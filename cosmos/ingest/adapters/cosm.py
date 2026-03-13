"""COSM C360 camera adapter.

Wraps the existing manifest parser, segment validator, and quad-tile
filter-graph builder behind the ``IngestAdapter`` contract.  Behaviour
is identical to pre-adapter ingest for all existing COSM workflows.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from cosmos.ingest.adapter import ClipDescriptor, FfmpegInputSpec
from cosmos.ingest.manifest import (
    ClipInfo,
    ManifestParser,
    find_manifest,
)
from cosmos.ingest.validation import (
    ClipValidationResult,
    InputValidator,
    SegmentInfo,
    ValidationIssue,
    ValidationLevel,
)

logger = logging.getLogger(__name__)


def _clip_info_from_descriptor(clip: ClipDescriptor) -> ClipInfo:
    """Re-hydrate the COSM-specific ``ClipInfo`` stashed in *clip.extra*."""
    ci: ClipInfo | None = clip.extra.get("_clip_info")  # type: ignore[assignment]
    if ci is None:
        raise ValueError(f"ClipDescriptor {clip.name!r} missing COSM _clip_info")
    return ci


class CosmAdapter:
    """Adapter for COSM C360 quad-tile TS-segment layouts."""

    @property
    def name(self) -> str:
        return "cosm"

    # -- detection -----------------------------------------------------------

    @staticmethod
    def detect(input_dir: Path) -> bool:
        """COSM layout is identified by a ``*.xml`` manifest in the root."""
        return find_manifest(input_dir) is not None

    # -- discovery -----------------------------------------------------------

    def discover_clips(self, input_dir: Path) -> list[ClipDescriptor]:
        manifest_path = find_manifest(input_dir)
        if manifest_path is None:
            return []
        parser = ManifestParser(manifest_path)
        descriptors: list[ClipDescriptor] = []
        for clip in parser.get_clips():
            descriptors.append(
                ClipDescriptor(
                    name=clip.name,
                    start_time_sec=clip.start_pos.to_seconds(),
                    end_time_sec=(clip.end_pos.to_seconds() if clip.end_pos else None),
                    frame_start=clip.start_idx,
                    frame_end=clip.end_idx,
                    extra={
                        "_clip_info": clip,
                        "_manifest_path": manifest_path,
                    },
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
        ci = _clip_info_from_descriptor(clip)
        manifest_path: Path = clip.extra["_manifest_path"]  # type: ignore[assignment]
        parser = ManifestParser(manifest_path)
        validator = InputValidator(input_dir, output_dir, parser)
        return validator.validate_clip(ci)

    # -- ffmpeg spec ---------------------------------------------------------

    def build_ffmpeg_spec(
        self,
        clip: ClipDescriptor,
        validation: ClipValidationResult,
        output_dir: Path,
        output_resolution: tuple[int, int],
        scale_filter: str,
    ) -> FfmpegInputSpec:
        concat_file = self._create_concat_file(validation.segments)
        filter_complex = self._build_filter_complex(output_resolution, scale_filter)
        return FfmpegInputSpec(
            input_args=["-f", "concat", "-safe", "0", "-i", concat_file],
            filter_complex=filter_complex,
            output_stem=clip.name,
            temp_files=[concat_file],
        )

    # -- system checks -------------------------------------------------------

    def validate_system(self, output_dir: Path) -> list[ValidationIssue]:
        return _default_validate_system(output_dir)

    # -- internal helpers (ported from processor.py) -------------------------

    @staticmethod
    def _build_filter_complex(
        output_resolution: tuple[int, int],
        scale_filter: str,
        crop_overlap: int = 32,
    ) -> str:
        """Quad-tile crop → hstack → vstack → scale."""
        tile = (
            f"[0:v:0]crop=iw-{crop_overlap}:ih-{crop_overlap}:0:0[tl];"
            f"[0:v:1]crop=iw-{crop_overlap}:ih-{crop_overlap}:{crop_overlap}:0[tr];"
            f"[0:v:2]crop=iw-{crop_overlap}:ih-{crop_overlap}:0:{crop_overlap}[bl];"
            f"[0:v:3]crop=iw-{crop_overlap}:ih-{crop_overlap}:{crop_overlap}:{crop_overlap}[br];"
            "[tl][tr]hstack=2[top];"
            "[bl][br]hstack=2[bottom];"
            "[top][bottom]vstack=2[full]"
        )
        w, h = output_resolution
        scale = f"[full]scale={w}:{h}:flags={scale_filter}[out]"
        return f"{tile};{scale}"

    @staticmethod
    def _create_concat_file(segments: list[SegmentInfo]) -> str:
        """Write an ffmpeg concat-demuxer manifest for ``.ts`` segments."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for segment in segments:
                for ts_file in segment.ts_files:
                    path_str = str(ts_file.absolute()).replace("\\", "/")
                    f.write(f"file '{path_str}'\n")
            return f.name


# ---------------------------------------------------------------------------
# Shared system-level validation (used by multiple adapters)
# ---------------------------------------------------------------------------


def _default_validate_system(output_dir: Path) -> list[ValidationIssue]:
    """Common pre-checks: ffmpeg presence, output dir writability."""
    import subprocess

    from cosmos.ffmpeg.detect import resolve_ffmpeg_path

    issues: list[ValidationIssue] = []
    try:
        ff = resolve_ffmpeg_path()
        subprocess.run([ff, "-version"], capture_output=True, check=True)  # noqa: S603
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message="FFmpeg not found or not working",
                help_text="Install FFmpeg and ensure it is on PATH",
            )
        )
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
    except Exception:  # noqa: BLE001
        issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message=f"Cannot write to output directory: {output_dir}",
                help_text="Check permissions and disk space",
            )
        )
    return issues
