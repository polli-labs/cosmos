from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoProbe:
    """Typed metadata for the first video stream in a source file."""

    source_path: Path
    width: int
    height: int
    duration_seconds: float | None = None
    fps: float | None = None
    frame_count: int | None = None
    codec_name: str | None = None
    codec_long_name: str | None = None
    format_name: str | None = None


@dataclass(frozen=True, slots=True)
class VideoFrameTimeline:
    """Exact decoded-frame identities in the video stream's integer time base."""

    source_path: Path
    time_base_numerator: int
    time_base_denominator: int
    pts_ticks: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RgbFrame:
    """A decoded RGB frame payload with source/request metadata."""

    source_path: Path
    requested_index: int | None
    requested_time_seconds: float | None
    resolved_index: int | None
    resolved_time_seconds: float | None
    width: int
    height: int
    rgb24: bytes


class CosmosVideoError(RuntimeError):
    """Base class for Cosmos video substrate failures."""


class VideoProbeError(CosmosVideoError):
    """Raised when video metadata cannot be probed."""


class VideoDecodeError(CosmosVideoError):
    """Raised when RGB frame extraction fails."""
