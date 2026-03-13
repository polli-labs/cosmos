from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from cosmos.ffmpeg.args import build_square_crop_args
from cosmos.ffmpeg.detect import (
    choose_encoder_for_video,
    ensure_ffmpeg_available,
)


@dataclass
class CropRunResult:
    args: list[str]
    encoder_used: str
    encoder_attempted: str


@dataclass
class SquareCropSpec:
    size: int = 1080
    center_x: float | None = None
    center_y: float | None = None
    # Offsets relative to the available margin (legacy squarecrop semantics)
    # range [-1,1]; offset_x=-1 => flush left, +1 => flush right; offset_y=-1 => top, +1 => bottom.
    offset_x: float | None = None
    offset_y: float | None = None
    start: float | None = None
    end: float | None = None


def build_crop_filter(spec: SquareCropSpec) -> str:
    """Return a crop filter string using either center or margin-relative offsets.

    - If offset_x/y are provided, use old squarecrop semantics:
      x = (iw - s)/2 + offset_x * (iw - s)/2
      y = (ih - s)/2 + offset_y * (ih - s)/2
    - Otherwise fall back to center_x/center_y (absolute 0..1 of frame).
    """
    s = spec.size
    if spec.offset_x is not None or spec.offset_y is not None:
        ox = spec.offset_x or 0.0
        oy = spec.offset_y or 0.0
        x = f"(iw-{s})/2 + ({ox}) * (iw-{s})/2"
        y = f"(ih-{s})/2 + ({oy}) * (ih-{s})/2"
        return f"crop={s}:{s}:({x}):({y})"
    # center-based crop: compute x,y from center ratios
    cx = spec.center_x if spec.center_x is not None else 0.5
    cy = spec.center_y if spec.center_y is not None else 0.5
    x = f"(iw*{cx})-({s}/2)"
    y = f"(ih*{cy})-({s}/2)"
    return f"crop={s}:{s}:({x}):({y})"


def plan_crops(videos: Iterable[Path], spec: SquareCropSpec) -> list[tuple[Path, str]]:
    flt = build_crop_filter(spec)
    return [(Path(v), flt) for v in videos]


def run_square_crop(
    input_video: Path,
    output_path: Path,
    spec: SquareCropSpec,
    *,
    prefer_hevc_hw: bool = False,
    dry_run: bool = False,
    encoder_override: str | None = None,
    threads: int | None = None,
    bitexact: bool = False,
) -> CropRunResult:
    """Run or return ffmpeg args for a single square crop job."""
    if encoder_override is not None:
        encoder, attempted = encoder_override, encoder_override
    elif dry_run:
        encoder, attempted = "libx264", "libx264"
    else:
        encoder, attempted = choose_encoder_for_video(input_video, prefer_hevc_hw=prefer_hevc_hw)
    crop_filter = build_crop_filter(spec)

    def _build_args(enc: str) -> list[str]:
        return build_square_crop_args(
            input_video,
            output_path,
            encoder=enc,
            crop_filter=crop_filter,
            start=spec.start,
            end=spec.end,
            threads=threads,
            bitexact=bitexact,
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
        logging.getLogger(__name__).warning(
            "hardware encoder %s failed (%s); retrying with libx264", encoder, exc
        )
        args = _build_args("libx264")
        subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
        return CropRunResult(args=args, encoder_used="libx264", encoder_attempted=attempted)
