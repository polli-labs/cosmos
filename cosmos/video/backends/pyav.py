from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cosmos.video.backends.base import VideoBackendUnavailable
from cosmos.video.types import VideoDecodeError, VideoProbe

_SEEK_WINDOW_SPANS = (180, 360, 720)
_SEEK_PENALTY_FRAMES = 24
_MIN_SEEK_SAVINGS_FRAMES = 60
_TIME_EPSILON_SECONDS = 1e-6
_MAX_UNTIMED_FRAMES = 3

_LOGGER = logging.getLogger(__name__)


class PyAvBackend:
    """Optional in-process PyAV backend for RGB frame extraction."""

    name = "pyav"

    def extract_index_frames(
        self,
        *,
        source_path: Path,
        indices: Sequence[int],
        frame_bytes: int,
        probe: VideoProbe,
    ) -> dict[int, bytes]:
        if not indices:
            return {}

        seek_groups = _plan_seek_groups(indices, probe)
        if seek_groups is not None:
            try:
                return _extract_seek_index_frames(
                    source_path=source_path,
                    groups=seek_groups,
                    frame_bytes=frame_bytes,
                    probe=probe,
                )
            except VideoDecodeError:
                pass

        return _extract_scan_index_frames(
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
        av = _import_av()
        try:
            with av.open(str(source_path)) as container:
                stream = _video_stream(container, source_path)
                seeked = _seek_to_time(container, stream, time_seconds, probe)
                untimed_frames = 0
                for decoded_index, frame in enumerate(container.decode(video=0)):
                    frame_time = _frame_time_seconds(frame)
                    if frame_time is None and probe.fps and not seeked:
                        frame_time = decoded_index / probe.fps
                    if frame_time is None:
                        untimed_frames += 1
                        if untimed_frames >= _MAX_UNTIMED_FRAMES:
                            raise VideoDecodeError(
                                "PyAV could not resolve decoded frame timestamps for "
                                f"{source_path}; cannot extract time {time_seconds:.6f}s "
                                "without frame time metadata or probed FPS."
                            )
                        continue
                    if frame_time + _TIME_EPSILON_SECONDS >= time_seconds:
                        return _rgb24_bytes(frame, expected_bytes=frame_bytes)
        except VideoDecodeError:
            raise
        except Exception as exc:
            raise VideoDecodeError(
                f"PyAV failed while extracting time {time_seconds:.6f}s from {source_path}: {exc}"
            ) from exc

        raise VideoDecodeError(
            f"PyAV could not decode a frame at or after time {time_seconds:.6f}s "
            f"from {source_path}."
        )


def _import_av() -> Any:
    try:
        return importlib.import_module("av")
    except ModuleNotFoundError as exc:
        raise VideoBackendUnavailable(
            "PyAV video backend is unavailable. Install the optional extra with "
            "`uv sync --extra video-av` or force `COSMOS_VIDEO_BACKEND=ffmpeg-cli`."
        ) from exc


def _extract_scan_index_frames(
    *,
    source_path: Path,
    indices: Sequence[int],
    frame_bytes: int,
) -> dict[int, bytes]:
    av = _import_av()
    wanted = set(indices)
    # Public decode passes _unique_sorted_indices(), so the tail is the scan stop index.
    max_index = indices[-1]
    extracted: dict[int, bytes] = {}
    try:
        with av.open(str(source_path)) as container:
            _video_stream(container, source_path)
            for decoded_index, frame in enumerate(container.decode(video=0)):
                if decoded_index in wanted:
                    extracted[decoded_index] = _rgb24_bytes(frame, expected_bytes=frame_bytes)
                    if len(extracted) == len(wanted):
                        return extracted
                if decoded_index > max_index:
                    break
    except VideoDecodeError:
        raise
    except Exception as exc:
        raise VideoDecodeError(
            f"PyAV failed while extracting frame indices {list(indices)!r} from {source_path}: {exc}"
        ) from exc

    missing = sorted(wanted - extracted.keys())
    raise VideoDecodeError(
        f"PyAV could not decode requested frame indices {missing!r} from {source_path}."
    )


def _extract_seek_index_frames(
    *,
    source_path: Path,
    groups: Sequence[Sequence[int]],
    frame_bytes: int,
    probe: VideoProbe,
) -> dict[int, bytes]:
    if not probe.fps:
        raise VideoDecodeError("PyAV seek extraction requires probed FPS metadata.")

    av = _import_av()
    extracted: dict[int, bytes] = {}
    try:
        with av.open(str(source_path)) as container:
            stream = _video_stream(container, source_path)
            for group in groups:
                extracted.update(
                    _decode_seek_group(
                        container=container,
                        stream=stream,
                        group=group,
                        frame_bytes=frame_bytes,
                        probe=probe,
                    )
                )
    except VideoDecodeError:
        raise
    except Exception as exc:
        raise VideoDecodeError(
            f"PyAV failed while extracting seek groups {list(map(list, groups))!r} "
            f"from {source_path}: {exc}"
        ) from exc

    missing = sorted({index for group in groups for index in group} - extracted.keys())
    if missing:
        raise VideoDecodeError(
            f"PyAV seek extraction could not decode requested frame indices {missing!r} "
            f"from {source_path}."
        )
    return extracted


def _decode_seek_group(
    *,
    container: Any,
    stream: Any,
    group: Sequence[int],
    frame_bytes: int,
    probe: VideoProbe,
) -> dict[int, bytes]:
    # _extract_seek_index_frames validates probe.fps before dispatching groups here.
    fps = probe.fps
    if fps is None:
        raise AssertionError("PyAV seek group dispatched without FPS metadata.")
    _seek_to_index(container, stream, group[0], probe)
    wanted = set(group)
    stop_after_index = group[-1] + max(3, int(round(fps)))
    extracted: dict[int, bytes] = {}

    for frame in container.decode(video=0):
        decoded_index = _frame_index(frame, fps)
        if decoded_index is None:
            raise VideoDecodeError(
                "PyAV seek extraction could not resolve decoded frame timestamps."
            )
        if decoded_index in wanted:
            extracted[decoded_index] = _rgb24_bytes(frame, expected_bytes=frame_bytes)
            if wanted.issubset(extracted.keys()):
                break
        if decoded_index > stop_after_index:
            break

    return extracted


def _plan_seek_groups(indices: Sequence[int], probe: VideoProbe) -> list[list[int]] | None:
    if not probe.fps:
        return None

    full_scan_cost = indices[-1] + 1
    best_groups: list[list[int]] | None = None
    best_cost = full_scan_cost

    for max_span in _SEEK_WINDOW_SPANS:
        groups = _group_indices_by_span(indices, max_span)
        seek_cost = sum(group[-1] - group[0] + 1 for group in groups) + (
            len(groups) * _SEEK_PENALTY_FRAMES
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


def _video_stream(container: Any, source_path: Path) -> Any:
    video_streams = container.streams.video
    if not video_streams:
        raise VideoDecodeError(f"PyAV found no video stream in {source_path}.")
    return video_streams[0]


def _seek_to_index(container: Any, stream: Any, index: int, probe: VideoProbe) -> None:
    if not probe.fps:
        return
    _seek_to_time(container, stream, index / probe.fps, probe)


def _seek_to_time(container: Any, stream: Any, time_seconds: float, probe: VideoProbe) -> bool:
    time_base = getattr(stream, "time_base", None)
    if time_base is None:
        _LOGGER.warning(
            "PyAV stream %s has no time_base while seeking to %.6fs in %s; "
            "decoding will continue from the current position.",
            getattr(stream, "index", "?"),
            time_seconds,
            probe.source_path,
        )
        return False
    target_pts = max(0, int(time_seconds / float(time_base)))
    container.seek(target_pts, stream=stream, backward=True)
    return True


def _frame_index(frame: Any, fps: float) -> int | None:
    frame_time = _frame_time_seconds(frame)
    if frame_time is None:
        return None
    if frame_time < 0:
        # Negative timestamps are pre-roll/non-display frames in some containers.
        return None
    return int(round(frame_time * fps))


def _frame_time_seconds(frame: Any) -> float | None:
    frame_time = getattr(frame, "time", None)
    if frame_time is not None:
        return float(frame_time)

    pts = getattr(frame, "pts", None)
    time_base = getattr(frame, "time_base", None)
    if pts is None or time_base is None:
        return None
    return float(pts * time_base)


def _rgb24_bytes(frame: Any, *, expected_bytes: int) -> bytes:
    try:
        array = frame.to_ndarray(format="rgb24")
    except ModuleNotFoundError as exc:
        if exc.name == "numpy":
            raise VideoBackendUnavailable(
                "PyAV RGB extraction requires NumPy. Install the optional extra with "
                "`uv sync --extra video-av` or force `COSMOS_VIDEO_BACKEND=ffmpeg-cli`."
            ) from exc
        raise

    rgb24 = array.tobytes()
    if len(rgb24) != expected_bytes:
        raise VideoDecodeError(
            f"PyAV produced {len(rgb24)} RGB bytes; expected {expected_bytes}. "
            "Check probed dimensions and video decode support."
        )
    return rgb24


__all__ = ["PyAvBackend"]
