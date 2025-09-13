from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cosmos.crop.squarecrop import SquareCropSpec, plan_crops, run_square_crop


@dataclass
class CropJob:
    center_x: float = 0.5
    center_y: float = 0.5
    size: int = 1080
    start: float | None = None
    end: float | None = None


def crop(
    input_videos: list[Path],
    jobs: list[CropJob],
    out_dir: Path,
    *,
    ffmpeg_opts: dict[str, object] | None = None,
) -> list[Path]:
    """Return list of cropped video paths.

    Placeholder: does not run ffmpeg; simulates outputs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    # Apply only the first job for now
    job = jobs[0] if jobs else CropJob()
    spec = SquareCropSpec(size=job.size, center_x=job.center_x, center_y=job.center_y, start=job.start, end=job.end)
    dry_run = bool((ffmpeg_opts or {}).get("dry_run", False))
    _plan = plan_crops(input_videos, spec)
    for i, (src, _flt) in enumerate(_plan):
        out = out_dir / f"crop_{i:03d}.mp4"
        _ = run_square_crop(src, out, spec, dry_run=dry_run)
        if dry_run:
            # Touch file to simulate output for tests or dry-run workflows
            out.write_bytes(b"")
        results.append(out)
    return results
