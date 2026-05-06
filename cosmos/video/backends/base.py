from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol

from cosmos.video.types import VideoDecodeError, VideoProbe

COSMOS_VIDEO_BACKEND_ENV = "COSMOS_VIDEO_BACKEND"
VideoBackendName = Literal["auto", "ffmpeg-cli", "pyav", "torchcodec"]


class VideoBackendUnavailable(VideoDecodeError):
    """Raised when an optional video backend cannot be used in this environment."""


class VideoDecodeBackend(Protocol):
    """Internal byte-extraction contract behind the public video SDK."""

    name: str

    def extract_index_frames(
        self,
        *,
        source_path: Path,
        indices: Sequence[int],
        frame_bytes: int,
        probe: VideoProbe,
    ) -> dict[int, bytes]:
        """Return unique RGB frame bytes keyed by decoded frame index."""

    def extract_time_frame(
        self,
        *,
        source_path: Path,
        time_seconds: float,
        frame_bytes: int,
        probe: VideoProbe,
    ) -> bytes:
        """Return the first RGB frame bytes at or after a source timestamp."""
