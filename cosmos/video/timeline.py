from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from cosmos.ffmpeg.detect import resolve_ffprobe_path
from cosmos.video._helpers import (
    _clean_stderr,
    _coerce_source_path,
    _format_timeout,
    _video_subprocess_timeout_seconds,
)
from cosmos.video.types import VideoFrameTimeline, VideoProbeError

_INTEGER_PATTERN = re.compile(r"[+-]?\d+\Z")


def probe_video_timeline(path: Path | str) -> VideoFrameTimeline:
    """Return exact PTS ticks for decoded video frames in decoded-frame order.

    The returned ticks are expressed in the first video stream's reported time
    base. FFprobe's frame ``pts`` field is the sole identity authority. The
    function fails closed rather than substituting estimated timestamps or
    inventing identities for missing, malformed, duplicate, or nonmonotonic
    frame timestamps.
    """

    source_path = _coerce_source_path(path, error_cls=VideoProbeError)
    try:
        ffprobe = resolve_ffprobe_path()
    except Exception as exc:
        raise VideoProbeError(f"Could not resolve ffprobe for {source_path}: {exc}") from exc

    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_streams",
        "-show_frames",
        "-show_entries",
        "stream=time_base:frame=pts",
        "-of",
        "json",
        str(source_path),
    ]
    timeout = _video_subprocess_timeout_seconds()
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoProbeError(
            f"ffprobe timed out after {_format_timeout(timeout)} while reading the decoded "
            f"frame timeline from {source_path}."
        ) from exc
    except OSError as exc:
        raise VideoProbeError(
            f"ffprobe could not be launched at {ffprobe!r}. "
            "Install ffprobe or set COSMOS_FFPROBE to a valid executable."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = _clean_stderr(exc.stderr)
        raise VideoProbeError(
            f"ffprobe timeline probe failed for {source_path} "
            f"with exit code {exc.returncode}: {stderr}"
        ) from exc

    try:
        payload: Any = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoProbeError(
            f"ffprobe returned invalid timeline JSON for {source_path}: {exc}"
        ) from exc
    return _parse_video_frame_timeline_payload(payload, source_path=source_path)


def _parse_video_frame_timeline_payload(
    payload: object,
    *,
    source_path: Path,
) -> VideoFrameTimeline:
    if not isinstance(payload, dict):
        raise VideoProbeError(f"ffprobe returned an invalid timeline payload for {source_path}")
    payload_mapping = cast(dict[str, object], payload)

    streams = payload_mapping.get("streams")
    if not isinstance(streams, list) or not streams:
        raise VideoProbeError(f"No video stream found in {source_path}")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise VideoProbeError(f"ffprobe returned an invalid video stream for {source_path}")
    stream_mapping = cast(dict[str, object], stream)
    time_base_numerator, time_base_denominator = _parse_time_base(
        stream_mapping.get("time_base"),
        source_path=source_path,
    )

    frames = payload_mapping.get("frames")
    if not isinstance(frames, list) or not frames:
        raise VideoProbeError(f"No decoded video frames found in {source_path}")

    ticks: list[int] = []
    previous_tick: int | None = None
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise VideoProbeError(
                f"ffprobe returned an invalid decoded frame at index {frame_index} "
                f"for {source_path}"
            )
        frame_mapping = cast(dict[str, object], frame)
        raw_tick = frame_mapping.get("pts")
        if raw_tick is None or raw_tick == "N/A":
            raise VideoProbeError(
                f"Decoded frame {frame_index} has no PTS identity in {source_path}"
            )
        tick = _parse_integer_tick(
            raw_tick,
            field_name="pts",
            frame_index=frame_index,
            source_path=source_path,
        )
        if previous_tick is not None and tick <= previous_tick:
            relation = "duplicate" if tick == previous_tick else "nonmonotonic"
            raise VideoProbeError(
                f"Decoded frame {frame_index} has {relation} PTS tick {tick} "
                f"after {previous_tick} in {source_path}"
            )
        ticks.append(tick)
        previous_tick = tick

    return VideoFrameTimeline(
        source_path=source_path,
        time_base_numerator=time_base_numerator,
        time_base_denominator=time_base_denominator,
        pts_ticks=tuple(ticks),
    )


def _parse_time_base(value: object, *, source_path: Path) -> tuple[int, int]:
    if not isinstance(value, str):
        raise VideoProbeError(f"Video stream has no usable time_base in {source_path}")
    parts = value.split("/")
    if len(parts) != 2:
        raise VideoProbeError(f"Video stream has invalid time_base {value!r} in {source_path}")
    numerator = _parse_integer_text(parts[0])
    denominator = _parse_integer_text(parts[1])
    if numerator is None or denominator is None or numerator <= 0 or denominator <= 0:
        raise VideoProbeError(f"Video stream has invalid time_base {value!r} in {source_path}")
    return numerator, denominator


def _parse_integer_tick(
    value: object,
    *,
    field_name: str,
    frame_index: int,
    source_path: Path,
) -> int:
    if isinstance(value, bool):
        parsed = None
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        parsed = _parse_integer_text(value)
    else:
        parsed = None
    if parsed is None:
        raise VideoProbeError(
            f"Decoded frame {frame_index} has non-integral {field_name}={value!r} in {source_path}"
        )
    return parsed


def _parse_integer_text(value: str) -> int | None:
    if _INTEGER_PATTERN.fullmatch(value) is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


__all__ = ["probe_video_timeline"]
