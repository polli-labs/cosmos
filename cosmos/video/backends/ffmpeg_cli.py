from __future__ import annotations

import json
import logging
import math
import subprocess
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from cosmos.ffmpeg.detect import resolve_ffmpeg_path, resolve_ffprobe_path
from cosmos.video._helpers import (
    _clean_stderr,
    _format_timeout,
    _video_subprocess_timeout_seconds,
)
from cosmos.video.types import VideoDecodeError, VideoProbe

_MAX_SELECT_EXPRESSION_CHARS = 16_000
_SEEK_WINDOW_SPANS = (180, 360, 720)
_SEEK_PROCESS_PENALTY_FRAMES = 120
_SEEK_TIMESTAMP_PROBE_PENALTY_FRAMES = 60
_MIN_SEEK_SAVINGS_FRAMES = 120

_LOGGER = logging.getLogger(__name__)


class FfmpegCliBackend:
    """FFmpeg/ffprobe subprocess backend for portable RGB frame extraction."""

    name = "ffmpeg-cli"

    def extract_index_frames(
        self,
        *,
        source_path: Path,
        indices: Sequence[int],
        frame_bytes: int,
        probe: VideoProbe,
    ) -> dict[int, bytes]:
        # The CLI backend shells out to ffmpeg/ffprobe and does not need caller probe metadata.
        del probe
        return _extract_unique_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
        )

    def extract_time_frame(
        self,
        *,
        source_path: Path,
        time_seconds: float,
        frame_bytes: int,
        probe: VideoProbe,
    ) -> bytes:
        del probe
        return _run_ffmpeg_rawvideo(
            _frame_time_command(source_path, time_seconds),
            source_path=source_path,
            request=f"time {time_seconds:.6f}s",
            expected_bytes=frame_bytes,
        )


def _extract_unique_index_frames(
    *,
    source_path: Path,
    indices: Sequence[int],
    frame_bytes: int,
) -> dict[int, bytes]:
    if not indices:
        return {}

    seek_groups = _plan_seek_groups(indices)
    if seek_groups is not None:
        try:
            return _extract_seek_index_frames(
                source_path=source_path,
                groups=seek_groups,
                frame_bytes=frame_bytes,
            )
        except VideoDecodeError as exc:
            _LOGGER.debug(
                "Seek-based FFmpeg extraction failed for %s; falling back to scan: %s",
                source_path,
                exc,
            )

    return _extract_scan_index_frames(
        source_path=source_path,
        indices=indices,
        frame_bytes=frame_bytes,
    )


def _extract_scan_index_frames(
    *,
    source_path: Path,
    indices: Sequence[int],
    frame_bytes: int,
) -> dict[int, bytes]:
    chunks = _chunk_indices_for_select(indices)
    if len(chunks) > 1:
        extracted: dict[int, bytes] = {}
        for chunk in chunks:
            extracted.update(
                _extract_scan_index_frames(
                    source_path=source_path,
                    indices=chunk,
                    frame_bytes=frame_bytes,
                )
            )
        return extracted

    request = _format_index_request(indices)
    rgb24 = _run_ffmpeg_rawvideo(
        _frame_indices_command(source_path, indices),
        source_path=source_path,
        request=request,
        expected_bytes=frame_bytes * len(indices),
    )
    return {
        index: rgb24[offset * frame_bytes : (offset + 1) * frame_bytes]
        for offset, index in enumerate(indices)
    }


def _extract_seek_index_frames(
    *,
    source_path: Path,
    groups: Sequence[Sequence[int]],
    frame_bytes: int,
) -> dict[int, bytes]:
    timestamps = _packet_timestamps_for_source(source_path)
    max_index = max(group[-1] for group in groups)
    if max_index >= len(timestamps):
        raise VideoDecodeError(
            f"ffprobe reported {len(timestamps)} packet timestamps for {source_path}; "
            f"cannot seek to frame index {max_index}."
        )

    extracted: dict[int, bytes] = {}
    for group in groups:
        start_index = group[0]
        offsets = [index - start_index for index in group]
        rgb24 = _run_ffmpeg_rawvideo(
            _seek_frame_indices_command(
                source_path,
                start_time_seconds=timestamps[start_index],
                offsets=offsets,
            ),
            source_path=source_path,
            request=_format_index_request(group),
            expected_bytes=frame_bytes * len(group),
        )
        extracted.update(
            {
                index: rgb24[offset * frame_bytes : (offset + 1) * frame_bytes]
                for offset, index in enumerate(group)
            }
        )
    return extracted


def _plan_seek_groups(indices: Sequence[int]) -> list[list[int]] | None:
    # Callers pass non-empty, ascending indices from decode.py's _unique_sorted_indices().
    full_scan_cost = indices[-1] + 1
    best_groups: list[list[int]] | None = None
    best_cost = full_scan_cost

    for max_span in _SEEK_WINDOW_SPANS:
        groups = _chunk_seek_groups(_group_indices_by_span(indices, max_span))
        seek_cost = (
            sum(group[-1] - group[0] + 1 for group in groups)
            + len(groups) * _SEEK_PROCESS_PENALTY_FRAMES
            + _SEEK_TIMESTAMP_PROBE_PENALTY_FRAMES
        )
        if seek_cost < best_cost:
            best_groups = groups
            best_cost = seek_cost

    if best_groups is None:
        return None
    if full_scan_cost - best_cost < _MIN_SEEK_SAVINGS_FRAMES:
        return None
    return best_groups


def _group_indices_by_span(indices: Sequence[int], max_span: int) -> list[list[int]]:
    groups: list[list[int]] = []
    current: list[int] = []
    for index in indices:
        if current and index - current[0] > max_span:
            groups.append(current)
            current = [index]
        else:
            current.append(index)
    if current:
        groups.append(current)
    return groups


def _chunk_seek_groups(groups: Sequence[Sequence[int]]) -> list[list[int]]:
    chunks: list[list[int]] = []
    for group in groups:
        chunks.extend(_chunk_indices_for_select(group))
    return chunks


def _format_index_request(indices: Sequence[int]) -> str:
    if len(indices) <= 8:
        return f"frame indices {list(indices)!r}"
    return f"{len(indices)} frame indices from {indices[0]} through {indices[-1]}"


def _chunk_indices_for_select(indices: Sequence[int]) -> list[list[int]]:
    chunks: list[list[int]] = []
    current: list[int] = []
    current_chars = 0

    for index in indices:
        term_chars = len(_select_index_term(index))
        next_chars = current_chars + term_chars + (1 if current else 0)
        if current and next_chars > _MAX_SELECT_EXPRESSION_CHARS:
            chunks.append(current)
            current = [index]
            current_chars = term_chars
        else:
            current.append(index)
            current_chars = next_chars

    if current:
        chunks.append(current)
    return chunks


def _select_index_term(index: int) -> str:
    return f"eq(n\\,{index})"


def _frame_indices_command(source_path: Path, indices: Sequence[int]) -> list[str]:
    select_expression = "+".join(_select_index_term(index) for index in indices)
    return [
        resolve_ffmpeg_path(),
        "-v",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"select={select_expression}",
        "-fps_mode",
        "passthrough",
        "-frames:v",
        str(len(indices)),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]


def _seek_frame_indices_command(
    source_path: Path,
    *,
    start_time_seconds: float,
    offsets: Sequence[int],
) -> list[str]:
    select_expression = "+".join(_select_index_term(offset) for offset in offsets)
    return [
        resolve_ffmpeg_path(),
        "-v",
        "error",
        "-accurate_seek",
        "-ss",
        f"{start_time_seconds:.9f}",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"select={select_expression}",
        "-fps_mode",
        "passthrough",
        "-frames:v",
        str(len(offsets)),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]


def _frame_time_command(source_path: Path, time_seconds: float) -> list[str]:
    return [
        resolve_ffmpeg_path(),
        "-v",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"select=gte(t\\,{time_seconds:.6f})",
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]


def _packet_timestamps_for_source(source_path: Path) -> tuple[float, ...]:
    stat = source_path.stat()
    return _packet_timestamps_for_source_cached(
        str(source_path),
        stat.st_size,
        stat.st_mtime_ns,
    )


@lru_cache(maxsize=32)
def _packet_timestamps_for_source_cached(
    source_path_raw: str,
    source_size: int,
    source_mtime_ns: int,
) -> tuple[float, ...]:
    del source_size, source_mtime_ns
    source_path = Path(source_path_raw)
    stdout = _run_ffprobe_packet_timestamps(source_path)

    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoDecodeError(
            f"ffprobe returned invalid packet timestamp JSON for {source_path}: {exc}"
        ) from exc

    packets = payload.get("packets")
    if not isinstance(packets, list):
        raise VideoDecodeError(f"ffprobe did not return packet timestamps for {source_path}.")

    timestamps: list[float] = []
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        raw = packet.get("pts_time")
        try:
            timestamp = float(str(raw))
        except (TypeError, ValueError):
            continue
        if math.isfinite(timestamp):
            timestamps.append(timestamp)

    if not timestamps:
        raise VideoDecodeError(
            f"ffprobe did not report usable packet timestamps for {source_path}."
        )
    return tuple(sorted(timestamps))


def _run_ffprobe_packet_timestamps(source_path: Path) -> str:
    timeout = _video_subprocess_timeout_seconds()
    ffprobe = "ffprobe"
    try:
        ffprobe = resolve_ffprobe_path()
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=pts_time",
            "-of",
            "json",
            str(source_path),
        ]
        completed = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoDecodeError(
            f"ffprobe timed out after {_format_timeout(timeout)} while reading packet "
            f"timestamps from {source_path}."
        ) from exc
    except FileNotFoundError as exc:
        raise VideoDecodeError(
            f"ffprobe could not be launched at {ffprobe!r}. "
            "Install ffprobe or set COSMOS_FFPROBE to a valid executable."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = _clean_stderr(exc.stderr)
        raise VideoDecodeError(
            f"ffprobe failed while reading packet timestamps from {source_path} "
            f"with exit code {exc.returncode}: {stderr}"
        ) from exc
    except Exception as exc:
        raise VideoDecodeError(
            f"ffprobe could not be resolved while reading packet timestamps "
            f"from {source_path}: {exc}"
        ) from exc
    return completed.stdout if isinstance(completed.stdout, str) else ""


def _run_ffmpeg_rawvideo(
    cmd: list[str],
    *,
    source_path: Path,
    request: str,
    expected_bytes: int,
) -> bytes:
    timeout = _video_subprocess_timeout_seconds()
    try:
        completed = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoDecodeError(
            f"ffmpeg timed out after {_format_timeout(timeout)} while extracting "
            f"{request} from {source_path}."
        ) from exc
    except FileNotFoundError as exc:
        ffmpeg = cmd[0] if cmd else "ffmpeg"
        raise VideoDecodeError(
            f"ffmpeg could not be launched at {ffmpeg!r}. "
            "Install ffmpeg or set COSMOS_FFMPEG to a valid executable."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = _clean_stderr(exc.stderr)
        raise VideoDecodeError(
            f"ffmpeg failed while extracting {request} from {source_path} "
            f"with exit code {exc.returncode}: {stderr}"
        ) from exc

    rgb24 = completed.stdout
    if not isinstance(rgb24, bytes):
        raise VideoDecodeError(
            f"ffmpeg returned non-bytes output for {request} from {source_path}."
        )
    if len(rgb24) != expected_bytes:
        raise VideoDecodeError(
            f"ffmpeg produced {len(rgb24)} bytes for {request} from {source_path}; "
            f"expected {expected_bytes} bytes. Check that the requested frame exists "
            "and the video is decodable."
        )
    return rgb24


__all__ = ["FfmpegCliBackend"]
