from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from cosmos.ffmpeg.args import build_square_crop_args
from cosmos.ffmpeg.detect import choose_encoder, ensure_ffmpeg_available


@dataclass
class SquareCropSpec:
    size: int = 1080
    center_x: float = 0.5
    center_y: float = 0.5
    start: float | None = None
    end: float | None = None


def build_crop_filter(spec: SquareCropSpec) -> str:
    """Return a simple crop filter string for ffmpeg."""
    s = spec.size
    # center-based crop: compute x,y from center ratios
    x = f"(iw*{spec.center_x})-({s}/2)"
    y = f"(ih*{spec.center_y})-({s}/2)"
    return f"crop={s}:{s}:{x}:{y}"


def plan_crops(videos: Iterable[Path], spec: SquareCropSpec) -> list[tuple[Path, str]]:
    flt = build_crop_filter(spec)
    return [(Path(v), flt) for v in videos]


def run_square_crop(
    input_video: Path,
    output_path: Path,
    spec: SquareCropSpec,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Run or return ffmpeg args for a single square crop job."""
    ensure_ffmpeg_available()
    encoder = choose_encoder() if not dry_run else "libx264"
    args = build_square_crop_args(
        input_video,
        output_path,
        encoder=encoder,
        crop_filter=build_crop_filter(spec),
        start=spec.start,
        end=spec.end,
    )
    if not dry_run:
        subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
    return args
