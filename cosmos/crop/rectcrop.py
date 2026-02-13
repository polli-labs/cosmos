from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cosmos.crop.squarecrop import CropRunResult
from cosmos.ffmpeg.detect import (
    _probe_dimensions,
    choose_encoder_for_video,
    ensure_ffmpeg_available,
    resolve_ffmpeg_path,
)

logger = logging.getLogger(__name__)


@dataclass
class RectCropSpec:
    """Rectangular crop specification.

    Coordinates are normalized [0,1] by default (relative to source frame).
    Set ``normalized=False`` to pass pixel values directly.
    """

    x0: float
    y0: float
    w: float
    h: float
    normalized: bool = True
    start: float | None = None
    end: float | None = None


def _round_even(n: int) -> int:
    """Round down to the nearest even integer (ffmpeg requires even dims)."""
    return n - (n % 2)


def build_rect_crop_filter(
    spec: RectCropSpec,
    source_w: int,
    source_h: int,
) -> str:
    """Return an ffmpeg crop filter string ``crop=W:H:X:Y``.

    For normalized specs, computes pixel values, clamps to frame bounds,
    and forces even W/H (ffmpeg requirement).
    """
    if spec.normalized:
        x_px = int(spec.x0 * source_w)
        y_px = int(spec.y0 * source_h)
        w_px = int(spec.w * source_w)
        h_px = int(spec.h * source_h)
    else:
        x_px = int(spec.x0)
        y_px = int(spec.y0)
        w_px = int(spec.w)
        h_px = int(spec.h)

    # Clamp to frame bounds
    if x_px + w_px > source_w:
        w_px = source_w - x_px
    if y_px + h_px > source_h:
        h_px = source_h - y_px
    x_px = max(0, x_px)
    y_px = max(0, y_px)

    # Force even dimensions
    w_px = _round_even(w_px)
    h_px = _round_even(h_px)

    return f"crop={w_px}:{h_px}:{x_px}:{y_px}"


def _build_rect_crop_args(
    input_path: Path,
    output_path: Path,
    *,
    encoder: str,
    crop_filter: str,
    start: float | None = None,
    end: float | None = None,
) -> list[str]:
    """Build ffmpeg args for a rectangular crop — mirrors build_square_crop_args."""
    args: list[str] = [resolve_ffmpeg_path(), "-y"]
    if start is not None:
        args += ["-ss", f"{start}"]
    args += ["-i", str(input_path)]
    if end is not None:
        args += ["-to", f"{end}"]
    args += [
        "-vf",
        crop_filter,
        "-c:v",
        encoder,
        "-crf",
        "18",
        "-an",
        str(output_path),
    ]
    return args


def run_rect_crop(
    input_video: Path,
    output_path: Path,
    spec: RectCropSpec,
    *,
    source_w: int | None = None,
    source_h: int | None = None,
    prefer_hevc_hw: bool = False,
    dry_run: bool = False,
) -> CropRunResult:
    """Run or return ffmpeg args for a single rectangular crop job."""
    # Probe source dimensions if not provided
    if source_w is None or source_h is None:
        probed_w, probed_h = _probe_dimensions(input_video)
        if probed_w is None or probed_h is None:
            raise ValueError(
                f"Could not determine dimensions for {input_video}; "
                "pass source_w/source_h explicitly"
            )
        source_w = probed_w
        source_h = probed_h

    encoder, attempted = (
        ("libx264", "libx264")
        if dry_run
        else choose_encoder_for_video(input_video, prefer_hevc_hw=prefer_hevc_hw)
    )

    crop_filter = build_rect_crop_filter(spec, source_w, source_h)

    def _build_args(enc: str) -> list[str]:
        return _build_rect_crop_args(
            input_video,
            output_path,
            encoder=enc,
            crop_filter=crop_filter,
            start=spec.start,
            end=spec.end,
        )

    args = _build_args(encoder)
    if dry_run:
        return CropRunResult(args=args, encoder_used=encoder, encoder_attempted=attempted)

    ensure_ffmpeg_available()

    try:
        subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
        return CropRunResult(args=args, encoder_used=encoder, encoder_attempted=attempted)
    except subprocess.CalledProcessError as exc:
        if encoder == "libx264":
            raise
        logger.warning("hardware encoder %s failed (%s); retrying with libx264", encoder, exc)
        args = _build_args("libx264")
        subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
        return CropRunResult(args=args, encoder_used="libx264", encoder_attempted=attempted)
