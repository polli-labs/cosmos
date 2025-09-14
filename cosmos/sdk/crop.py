from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cosmos.crop.squarecrop import SquareCropSpec, plan_crops, run_square_crop
from cosmos.sdk.provenance import emit_crop_run, emit_crop_view


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
    # Emit run-level provenance
    jobs_summary = [
        {
            "center_x": j.center_x,
            "center_y": j.center_y,
            "size": j.size,
            "start": j.start,
            "end": j.end,
        }
        for j in (jobs or [])
    ]
    crop_run_id, _run_path = emit_crop_run(output_dir=out_dir, jobs=jobs_summary)
    results: list[Path] = []
    # Apply only the first job for now
    job = jobs[0] if jobs else CropJob()
    spec = SquareCropSpec(size=job.size, center_x=job.center_x, center_y=job.center_y, start=job.start, end=job.end)
    dry_run = bool((ffmpeg_opts or {}).get("dry_run", False))
    _plan = plan_crops(input_videos, spec)
    for i, (src, _flt) in enumerate(_plan):
        out = out_dir / f"crop_{i:03d}.mp4"
        args = run_square_crop(src, out, spec, dry_run=dry_run)
        if dry_run:
            # Touch file to simulate output for tests or dry-run workflows
            out.write_bytes(b"")
        else:
            # Emit per-view provenance
            try:
                enc = None
                if "-c:v" in args:
                    idx = args.index("-c:v")
                    if idx + 1 < len(args):
                        enc = args[idx + 1]
                emit_crop_view(
                    crop_run_id=crop_run_id,
                    source_path=src,
                    output_path=out,
                    crop_spec={
                        "size": spec.size,
                        "center_x": spec.center_x,
                        "center_y": spec.center_y,
                        "start": spec.start if spec.start is not None else None,
                        "end": spec.end if spec.end is not None else None,
                    },
                    encode_info={"impl": enc},
                    job_ref=f"job0",
                )
            except Exception:
                pass
        results.append(out)
    return results
