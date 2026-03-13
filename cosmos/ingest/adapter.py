"""Ingest adapter contract.

An ``IngestAdapter`` encapsulates everything source-layout-specific about
a video ingest run: how clips are discovered, validated, and turned into
ffmpeg commands.  The generic ingest orchestrator (``cosmos.sdk.ingest``)
calls the adapter methods in order and stays layout-agnostic.

Adapters are selected via ``resolve_adapter()`` which either honours an
explicit ``--adapter`` CLI flag or auto-detects based on directory contents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from cosmos.ingest.validation import ClipValidationResult, ValidationIssue

# ---------------------------------------------------------------------------
# Generic clip descriptor (adapter-agnostic)
# ---------------------------------------------------------------------------


@dataclass
class ClipDescriptor:
    """Layout-agnostic clip metadata returned by an adapter's ``discover_clips``.

    Fields mirror the subset of ``ClipInfo`` that the orchestrator needs.
    Adapters may attach extra data in ``extra`` for their own use (e.g. the
    COSM ``Position`` objects).
    """

    name: str
    start_time_sec: float
    end_time_sec: float | None = None
    frame_start: int = 0
    frame_end: int = 0
    extra: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ffmpeg input specification (adapter → processor)
# ---------------------------------------------------------------------------


@dataclass
class FfmpegInputSpec:
    """Everything the generic video processor needs to build an ffmpeg command.

    Adapters produce this; the processor consumes it.
    """

    input_args: list[str]
    """Pre-input arguments (e.g. ``['-f', 'concat', '-safe', '0', '-i', '/tmp/list.txt']``)."""

    filter_complex: str | None = None
    """Optional ``-filter_complex`` value.  ``None`` ⟹ no filter graph."""

    output_stem: str = ""
    """Desired output filename stem (without extension).  Defaults to clip name."""

    extra_output_args: list[str] = field(default_factory=list)
    """Additional output-side args injected before the output path."""

    temp_files: list[str] = field(default_factory=list)
    """Temp files created by the adapter that the processor should clean up."""


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class IngestAdapter(Protocol):
    """Protocol every ingest adapter must satisfy.

    The orchestrator calls these methods in the order listed.
    """

    @property
    def name(self) -> str:
        """Short identifier (e.g. ``'cosm'``, ``'generic-media'``)."""
        ...

    # -- 1. detection ---------------------------------------------------------

    @staticmethod
    def detect(input_dir: Path) -> bool:
        """Return ``True`` if *input_dir* looks like this adapter's layout.

        Called during auto-detection; should be cheap (stat / glob, no parsing).
        """
        ...

    # -- 2. discovery ---------------------------------------------------------

    def discover_clips(self, input_dir: Path) -> list[ClipDescriptor]:
        """Enumerate clips available in *input_dir*.

        For sources without a clip concept (e.g. a flat directory of MP4s)
        each file may be treated as a single "clip".
        """
        ...

    # -- 3. validation --------------------------------------------------------

    def validate_clip(
        self,
        clip: ClipDescriptor,
        input_dir: Path,
        output_dir: Path,
    ) -> ClipValidationResult:
        """Validate a single clip and return segments + issues.

        Adapters should populate ``ClipValidationResult.segments`` even when
        the source is a simple file (one segment = the file itself).
        """
        ...

    # -- 4. ffmpeg spec -------------------------------------------------------

    def build_ffmpeg_spec(
        self,
        clip: ClipDescriptor,
        validation: ClipValidationResult,
        output_dir: Path,
        output_resolution: tuple[int, int],
        scale_filter: str,
    ) -> FfmpegInputSpec:
        """Build the ffmpeg input specification for a validated clip.

        The generic processor adds encoder settings, thread management, and
        the output path; the adapter controls input demux and filtergraph.
        """
        ...

    # -- 5. system-level checks (optional, has default) -----------------------

    def validate_system(self, output_dir: Path) -> list[ValidationIssue]:
        """Optional system-level pre-checks (e.g. ffmpeg availability).

        The base implementation in ``_default_validate_system`` handles the
        common ffmpeg + disk checks.  Override only when adapter-specific
        system requirements exist.
        """
        ...
