from __future__ import annotations

import json
import logging
import shutil
import subprocess

# ruff: noqa: UP035
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .manifest import ClipInfo, ClipStatus, ManifestParser, Position


class ValidationLevel(Enum):
    """Severity level for validation issues"""

    ERROR = "error"  # Fatal issue, cannot proceed
    WARNING = "warning"  # Potential issue, can proceed with caution
    INFO = "info"  # Informational note


@dataclass
class ValidationIssue:
    """Details about a validation problem"""

    level: ValidationLevel
    message: str
    context: str | None = None
    help_text: str | None = None


@dataclass
class SegmentInfo:
    """Information about a video segment from meta.json"""

    directory: Path
    start_time: float
    frame_timestamps: list[float]
    ts_files: list[Path]

    @property
    def end_time(self) -> float:
        """Get end time of segment from last frame timestamp"""
        return self.frame_timestamps[-1] if self.frame_timestamps else self.start_time

    @property
    def frame_count(self) -> int:
        """Number of frames in segment"""
        return len(self.frame_timestamps)

    @property
    def duration(self) -> float:
        """Approximate duration based on ts_files count (each ts represents 0.1s)"""
        return len(self.ts_files) * 0.1


@dataclass
class ClipValidationResult:
    """Validation results for a single clip"""

    clip: ClipInfo
    segments: list[SegmentInfo]
    missing_segments: list[Position]
    issues: list[ValidationIssue]
    estimated_size: int  # in bytes

    @property
    def is_valid(self) -> bool:
        """Check if clip has enough valid data to process"""
        return bool(self.segments) and not any(
            issue.level == ValidationLevel.ERROR for issue in self.issues
        )


@dataclass
class ValidationResult:
    """Complete validation results for input directory"""

    system_issues: list[ValidationIssue]
    clip_results: dict[str, ClipValidationResult]
    total_size_estimate: int
    available_space: int

    @property
    def can_proceed(self) -> bool:
        """Check if processing can proceed with any clips"""
        return (
            not any(i.level == ValidationLevel.ERROR for i in self.system_issues)
            and any(r.is_valid for r in self.clip_results.values())
            and self.available_space > self.total_size_estimate
        )


class InputValidator:
    """
    Validates input data and system requirements for COSM video processing.

    Performs checks at multiple levels:
    1. System requirements (ffmpeg, space, etc.)
    2. Input directory structure
    3. Clip data integrity
    4. Segment availability and validity
    """

    def __init__(self, input_dir: Path, output_dir: Path, manifest_parser: ManifestParser):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.manifest_parser = manifest_parser
        self.logger = logging.getLogger(__name__)

    def validate_system(self) -> list[ValidationIssue]:
        """Check system requirements"""
        issues = []

        # Check ffmpeg installation
        try:
            ff = shutil.which("ffmpeg") or "ffmpeg"
            subprocess.run([ff, "-version"], capture_output=True, check=True)  # noqa: S603,S607
        except subprocess.CalledProcessError:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="FFmpeg not found",
                    help_text="Please install FFmpeg to process videos",
                )
            )
        except FileNotFoundError:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="FFmpeg not found in system PATH",
                    help_text="Please install FFmpeg and ensure it's in your PATH",
                )
            )

        # Check output directory
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.output_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:  # noqa: BLE001
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Cannot write to output directory: {e}",
                    help_text="Check permissions and disk space",
                )
            )

        return issues

    def load_segment(self, segment_dir: Path) -> SegmentInfo | None:
        """
        Load a segment directory and its meta.json without FPS checks yet.

        Args:
            segment_dir: Path to segment directory

        Returns:
            SegmentInfo if valid, None if invalid
        """
        meta_path = segment_dir / "meta.json"
        self.logger.debug(f"Loading segment at {segment_dir}")

        if not meta_path.is_file():
            self.logger.debug(f"No meta.json found in {segment_dir}")
            return None

        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
                self.logger.debug(f"Loaded meta.json: {meta}")

            if "Time" not in meta or "x0" not in meta["Time"] or "xi-x0" not in meta["Time"]:
                self.logger.error(f"Invalid meta.json structure in {segment_dir}")
                return None

            start_time = meta["Time"]["x0"]
            increments = meta["Time"]["xi-x0"]

            # Get all .ts files in directory
            ts_files = sorted(segment_dir.glob("*.ts"))
            self.logger.debug(f"Found {len(ts_files)} .ts files in {segment_dir}")

            # Create timestamps for each frame
            timestamps = [start_time + inc for inc in increments]

            self.logger.debug(
                f"Segment loaded: start_time={start_time}, "
                f"frame_count={len(timestamps)}, file_count={len(ts_files)}"
            )

            return SegmentInfo(
                directory=segment_dir,
                start_time=start_time,
                frame_timestamps=timestamps,
                ts_files=ts_files,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning(f"Warning: failed to parse meta.json in {segment_dir}: {e}")
            return None

    def validate_clip(self, clip: ClipInfo) -> ClipValidationResult:  # noqa: C901
        """Validate all segments for a clip, delaying FPS checks until after end_epoch is known."""
        issues: list[ValidationIssue] = []
        segments: list[SegmentInfo] = []
        missing_positions: list[Position] = []

        self.logger.debug(f"Validating clip: {clip.name}")
        self.logger.debug(
            f"Clip boundaries: "
            f"start={clip.start_pos.to_string()}, "
            f"frames={clip.start_idx}-{clip.end_idx}"
        )

        start_sec = int(clip.start_pos.second)
        end_sec = int(clip.end_pos.second) if clip.end_pos else start_sec + 60
        total_positions = end_sec - start_sec + 1

        self.logger.debug(f"Scanning {total_positions} second positions")

        last_success_pos: Position | None = None
        for second in range(start_sec, end_sec + 1):
            pos = Position(hour=clip.start_pos.hour, minute=clip.start_pos.minute, second=second)

            segment_dir = self.input_dir / pos.path_fragment()
            self.logger.debug(f"Checking position {pos.to_string()} -> {segment_dir}")

            if not segment_dir.is_dir():
                self.logger.debug(f"Missing segment directory: {segment_dir}")
                missing_positions.append(pos)
                continue

            if segment_info := self.load_segment(segment_dir):
                self.logger.debug(
                    f"Segment loaded: {len(segment_info.ts_files)} files, "
                    f"{len(segment_info.frame_timestamps)} frames"
                )
                segments.append(segment_info)
                last_success_pos = pos
            else:
                self.logger.debug(f"Invalid segment at {segment_dir}")
                issues.append(
                    ValidationIssue(
                        level=ValidationLevel.WARNING,
                        message=f"Invalid segment at {pos.path_fragment()}",
                        context="Missing or corrupt meta.json",
                    )
                )

        # If we have segments, we can determine the end_epoch from the last segment
        if segments:
            # Update clip end based on last segment
            clip.end_epoch = segments[-1].end_time
            if last_success_pos:
                clip.end_pos = last_success_pos

        # Report segment coverage
        found_segments = len(segments)
        if found_segments == 0:
            self.logger.warning(f"No valid segments found for clip {clip.name}")
        else:
            coverage = (found_segments / total_positions) * 100
            self.logger.info(
                f"Clip {clip.name}: Found {found_segments}/{total_positions} "
                f"segments ({coverage:.1f}% coverage)"
            )
            for segment in segments:
                self.logger.debug(
                    f"Segment {segment.directory.name}: "
                    f"{len(segment.ts_files)} files, "
                    f"time range: {segment.start_time:.3f}-{segment.end_time:.3f}"
                )

        # Now that we potentially have end_epoch, we can compute FPS and verify increments
        if segments and clip.end_epoch is not None:
            try:
                clip_fps = clip.fps
                # Verify each segment against the derived FPS
                for seg in segments:
                    segment_duration_s = seg.duration
                    expected_frames = int(round(clip_fps * segment_duration_s))
                    if seg.frame_count != expected_frames:
                        issues.append(
                            ValidationIssue(
                                level=ValidationLevel.WARNING,
                                message=(
                                    f"Mismatch in {seg.directory}: expected {expected_frames} frames "
                                    f"(FPS={clip_fps}, duration={segment_duration_s:.1f}s) but got {seg.frame_count}."
                                ),
                            )
                        )
            except ValueError as e:
                # Cannot determine FPS for some reason
                issues.append(
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Cannot determine FPS for clip {clip.name}: {e}",
                    )
                )

        # Estimate output size (very rough)
        estimated_size = len(segments) * 100 * 1024 * 1024

        return ClipValidationResult(
            clip=clip,
            segments=segments,
            missing_segments=missing_positions,
            issues=issues,
            estimated_size=estimated_size,
        )

    def validate_all(self) -> ValidationResult:
        """
        Perform complete validation of system and input data

        Returns:
            ValidationResult with all validation details
        """
        # Check system requirements
        system_issues = self.validate_system()

        # Validate each clip
        clip_results: dict[str, ClipValidationResult] = {}
        total_size = 0

        for clip in self.manifest_parser.get_clips():
            result = self.validate_clip(clip)
            clip_results[clip.name] = result
            total_size += result.estimated_size

            # Update clip status based on validation
            if not result.segments:
                clip.status = ClipStatus.MISSING
            elif result.missing_segments:
                clip.status = ClipStatus.PARTIAL
            else:
                clip.status = ClipStatus.COMPLETE

        # Check available space
        try:
            available = shutil.disk_usage(self.output_dir).free
        except Exception:  # noqa: BLE001
            available = 0
            system_issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Cannot determine available disk space",
                    help_text="Check output directory permissions",
                )
            )

        return ValidationResult(
            system_issues=system_issues,
            clip_results=clip_results,
            total_size_estimate=total_size,
            available_space=available,
        )
