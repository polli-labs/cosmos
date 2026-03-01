"""Generic media adapter.

Handles directories of pre-existing video files (MP4, MOV, MKV, AVI, etc.)
that do not follow the COSM directory layout.  Each video file is treated
as a single "clip" and re-encoded through the standard Cosmos pipeline with
optional scaling but *no* tile-stitching filter graph.

This adapter serves two purposes:
1. Prove that the adapter contract is extensible beyond COSM.
2. Provide a useful baseline for ingesting arbitrary video collections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from cosmos.ingest.adapter import ClipDescriptor, FfmpegInputSpec
from cosmos.ingest.manifest import ClipInfo, ClipStatus, Position
from cosmos.ingest.validation import (
    ClipValidationResult,
    SegmentInfo,
    ValidationIssue,
    ValidationLevel,
)

logger = logging.getLogger(__name__)

# Extensions recognised as video files (case-insensitive).
_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".mov", ".mkv", ".avi", ".ts", ".mts", ".webm"}
)


def _is_video(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in _VIDEO_EXTENSIONS


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


@dataclass
class _FileClipExtra:
    """Stashed in ``ClipDescriptor.extra`` for roundtrip through the contract."""

    source_path: Path


class GenericMediaAdapter:
    """Adapter for flat directories containing video files."""

    @property
    def name(self) -> str:
        return "generic-media"

    # -- detection -----------------------------------------------------------

    @staticmethod
    def detect(input_dir: Path) -> bool:
        """Match any directory that contains at least one video file."""
        if not input_dir.is_dir():
            return False
        return any(_is_video(p) for p in input_dir.iterdir())

    # -- discovery -----------------------------------------------------------

    def discover_clips(self, input_dir: Path) -> list[ClipDescriptor]:
        videos = sorted(p for p in input_dir.iterdir() if _is_video(p))
        descriptors: list[ClipDescriptor] = []
        for video in videos:
            stem = video.stem
            descriptors.append(
                ClipDescriptor(
                    name=stem,
                    start_time_sec=0.0,
                    end_time_sec=None,  # unknown without probing
                    extra={"_source_path": video},
                )
            )
        return descriptors

    # -- validation ----------------------------------------------------------

    def validate_clip(
        self,
        clip: ClipDescriptor,
        input_dir: Path,
        output_dir: Path,
    ) -> ClipValidationResult:
        source: Path | None = clip.extra.get("_source_path")  # type: ignore[assignment]
        if source is None or not source.is_file():
            return ClipValidationResult(
                clip=self._make_clip_info(clip),
                segments=[],
                missing_segments=[],
                issues=[
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Source file not found: {source}",
                    )
                ],
                estimated_size=0,
            )

        # Treat the whole file as a single synthetic segment.
        seg = SegmentInfo(
            directory=source.parent,
            start_time=0.0,
            frame_timestamps=[0.0],
            ts_files=[source],
        )
        return ClipValidationResult(
            clip=self._make_clip_info(clip),
            segments=[seg],
            missing_segments=[],
            issues=[],
            estimated_size=_file_size(source),
        )

    # -- ffmpeg spec ---------------------------------------------------------

    def build_ffmpeg_spec(
        self,
        clip: ClipDescriptor,
        validation: ClipValidationResult,
        output_dir: Path,
        output_resolution: tuple[int, int],
        scale_filter: str,
    ) -> FfmpegInputSpec:
        source: Path = clip.extra["_source_path"]  # type: ignore[assignment]
        w, h = output_resolution
        return FfmpegInputSpec(
            input_args=["-i", str(source)],
            filter_complex=f"[0:v:0]scale={w}:{h}:flags={scale_filter}[out]",
            output_stem=clip.name,
        )

    # -- system checks -------------------------------------------------------

    def validate_system(self, output_dir: Path) -> list[ValidationIssue]:
        from cosmos.ingest.adapters.cosm import _default_validate_system

        return _default_validate_system(output_dir)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _make_clip_info(clip: ClipDescriptor) -> ClipInfo:
        """Build a ``ClipInfo`` compatible with provenance emission."""
        return ClipInfo(
            name=clip.name,
            start_epoch=clip.start_time_sec,
            end_epoch=clip.end_time_sec,
            start_pos=Position(hour=0, minute=0, second=clip.start_time_sec),
            end_pos=None,
            start_idx=clip.frame_start,
            end_idx=clip.frame_end,
            start_time=None,
            status=ClipStatus.COMPLETE,
        )
