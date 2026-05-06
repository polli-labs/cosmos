from __future__ import annotations

import math
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from cosmos.video._helpers import _coerce_source_path
from cosmos.video.backends.base import (
    COSMOS_VIDEO_BACKEND_ENV,
    VideoBackendName,
    VideoBackendUnavailable,
    VideoDecodeBackend,
)
from cosmos.video.backends.ffmpeg_cli import FfmpegCliBackend
from cosmos.video.backends.pyav import PyAvBackend
from cosmos.video.backends.torchcodec import TorchCodecBackend
from cosmos.video.probe import probe_video
from cosmos.video.types import RgbFrame, VideoDecodeError, VideoProbe

_FFMPEG_BACKEND: VideoDecodeBackend = FfmpegCliBackend()
_PYAV_BACKEND: VideoDecodeBackend = PyAvBackend()
_TORCHCODEC_BACKEND: VideoDecodeBackend = TorchCodecBackend()


def extract_frames_at_indices(
    path: Path | str,
    indices: Sequence[int],
    *,
    probe: VideoProbe | None = None,
) -> list[RgbFrame]:
    """Extract RGB frames by zero-based decoded frame index."""

    source_path = _coerce_source_path(path, error_cls=VideoDecodeError)
    requested = _validate_indices(indices)
    if not requested:
        return []
    video_probe = probe or probe_video(source_path)
    _validate_probe_dimensions(video_probe)
    _validate_known_index_bounds(source_path, requested, video_probe)

    frame_bytes = video_probe.width * video_probe.height * 3
    extracted = _extract_unique_index_frames(
        source_path=source_path,
        indices=_unique_sorted_indices(requested),
        frame_bytes=frame_bytes,
        probe=video_probe,
    )

    frames: list[RgbFrame] = []
    for index in requested:
        resolved_time = (index / video_probe.fps) if video_probe.fps else None
        frames.append(
            RgbFrame(
                source_path=source_path,
                requested_index=index,
                requested_time_seconds=None,
                resolved_index=index,
                resolved_time_seconds=resolved_time,
                width=video_probe.width,
                height=video_probe.height,
                rgb24=extracted[index],
            )
        )
    return frames


def extract_frames_at_times(
    path: Path | str,
    times_seconds: Sequence[float],
    *,
    probe: VideoProbe | None = None,
) -> list[RgbFrame]:
    """Extract RGB frames at or after requested source timestamps."""

    source_path = _coerce_source_path(path, error_cls=VideoDecodeError)
    requested = _validate_times(times_seconds)
    if not requested:
        return []
    video_probe = probe or probe_video(source_path)
    _validate_probe_dimensions(video_probe)
    _validate_known_time_bounds(source_path, requested, video_probe)

    frame_bytes = video_probe.width * video_probe.height * 3
    frames: list[RgbFrame] = []
    for time_seconds in requested:
        rgb24 = _extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=video_probe,
        )
        frames.append(
            RgbFrame(
                source_path=source_path,
                requested_index=None,
                requested_time_seconds=time_seconds,
                resolved_index=None,
                resolved_time_seconds=None,
                width=video_probe.width,
                height=video_probe.height,
                rgb24=rgb24,
            )
        )
    return frames


def _validate_indices(indices: Sequence[int]) -> list[int]:
    validated: list[int] = []
    for index in indices:
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError(f"Frame indices must be integers; got {index!r}")
        if index < 0:
            raise ValueError(f"Frame indices must be non-negative; got {index}")
        validated.append(index)
    return validated


def _validate_times(times_seconds: Sequence[float]) -> list[float]:
    validated: list[float] = []
    for time_seconds in times_seconds:
        value = float(time_seconds)
        if not math.isfinite(value):
            raise ValueError(f"Frame times must be finite seconds; got {time_seconds!r}")
        if value < 0:
            raise ValueError(f"Frame times must be non-negative seconds; got {value}")
        validated.append(value)
    return validated


def _validate_probe_dimensions(probe: VideoProbe) -> None:
    if probe.width <= 0 or probe.height <= 0:
        raise VideoDecodeError(
            f"Cannot extract frames from {probe.source_path}: "
            f"invalid probed dimensions {probe.width}x{probe.height}."
        )


def _validate_known_index_bounds(
    source_path: Path,
    indices: Sequence[int],
    probe: VideoProbe,
) -> None:
    if probe.frame_count is None:
        return
    for index in indices:
        if index >= probe.frame_count:
            raise ValueError(
                f"Frame index {index} is out of range for {source_path}; "
                f"frame_count={probe.frame_count}, valid range is 0..{probe.frame_count - 1}."
            )


def _validate_known_time_bounds(
    source_path: Path,
    times_seconds: Sequence[float],
    probe: VideoProbe,
) -> None:
    if probe.duration_seconds is None:
        return
    for time_seconds in times_seconds:
        if time_seconds > probe.duration_seconds:
            raise ValueError(
                f"Frame time {time_seconds:.6f}s is beyond {source_path}; "
                f"duration_seconds={probe.duration_seconds:.6f}."
            )


def _unique_sorted_indices(indices: Sequence[int]) -> list[int]:
    return sorted(set(indices))


def _extract_unique_index_frames(
    *,
    source_path: Path,
    indices: Sequence[int],
    frame_bytes: int,
    probe: VideoProbe,
) -> dict[int, bytes]:
    if not indices:
        return {}

    preference = _video_backend_preference()
    if preference == "ffmpeg-cli":
        return _FFMPEG_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    if preference == "pyav":
        return _PYAV_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    if preference == "torchcodec":
        return _TORCHCODEC_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )

    if preference == "auto":
        return _extract_auto_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    raise AssertionError(f"Unhandled video backend preference: {preference!r}")


def _extract_auto_index_frames(
    *,
    source_path: Path,
    indices: Sequence[int],
    frame_bytes: int,
    probe: VideoProbe,
) -> dict[int, bytes]:
    if _auto_backend_preference() == "ffmpeg-cli":
        return _FFMPEG_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )

    try:
        return _PYAV_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    except VideoBackendUnavailable:
        return _FFMPEG_BACKEND.extract_index_frames(
            source_path=source_path,
            indices=indices,
            frame_bytes=frame_bytes,
            probe=probe,
        )


def _extract_time_frame(
    *,
    source_path: Path,
    time_seconds: float,
    frame_bytes: int,
    probe: VideoProbe,
) -> bytes:
    preference = _video_backend_preference()
    if preference == "ffmpeg-cli":
        return _FFMPEG_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    if preference == "pyav":
        return _PYAV_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    if preference == "torchcodec":
        return _TORCHCODEC_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )

    if preference == "auto":
        return _extract_auto_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    raise AssertionError(f"Unhandled video backend preference: {preference!r}")


def _extract_auto_time_frame(
    *,
    source_path: Path,
    time_seconds: float,
    frame_bytes: int,
    probe: VideoProbe,
) -> bytes:
    if _auto_backend_preference() == "ffmpeg-cli":
        return _FFMPEG_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )

    try:
        return _PYAV_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )
    except VideoBackendUnavailable:
        return _FFMPEG_BACKEND.extract_time_frame(
            source_path=source_path,
            time_seconds=time_seconds,
            frame_bytes=frame_bytes,
            probe=probe,
        )


def _video_backend_preference() -> VideoBackendName:
    raw = os.environ.get(COSMOS_VIDEO_BACKEND_ENV)
    if raw is None:
        return "ffmpeg-cli"
    normalized = raw.strip().lower().replace("_", "-")
    if not normalized:
        return "ffmpeg-cli"
    if normalized == "auto":
        return "auto"
    if normalized in {"ffmpeg", "ffmpeg-cli"}:
        return "ffmpeg-cli"
    if normalized in {"av", "pyav"}:
        return "pyav"
    if normalized in {"tc", "torchcodec", "torch-codec"}:
        return "torchcodec"
    raise VideoDecodeError(
        f"Unsupported {COSMOS_VIDEO_BACKEND_ENV}={raw!r}; "
        "expected one of auto, ffmpeg-cli, pyav, or torchcodec."
    )


def _auto_backend_preference() -> VideoBackendName:
    """Pick the performance-safe backend for opt-in auto mode."""
    if sys.platform == "darwin":
        return "pyav"
    return "ffmpeg-cli"


__all__ = ["extract_frames_at_indices", "extract_frames_at_times"]
