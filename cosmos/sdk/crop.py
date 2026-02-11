from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cosmos.crop.squarecrop import SquareCropSpec, plan_crops, run_square_crop
from cosmos.sdk.provenance import emit_crop_run, emit_crop_view


@dataclass
class CropJob:
    center_x: float | None = None
    center_y: float | None = None
    offset_x: float | None = None
    offset_y: float | None = None
    size: int = 1080
    start: float | None = None
    end: float | None = None


def _normalize_offset(val: float | None) -> float | None:
    if val is None:
        return None
    if val < -1.0 or val > 1.0:
        raise ValueError(f"offset must be between -1 and 1 (got {val})")
    return val


def _validate_job(job: CropJob) -> None:
    if (job.offset_x is not None or job.offset_y is not None) and (
        job.center_x is not None or job.center_y is not None
    ):
        raise ValueError(
            "Provide either offsets or centers, not both. Offsets are margin-relative in [-1,1]."
        )
    if job.start is not None and job.end is not None and job.end <= job.start:
        raise ValueError("Invalid trim window: trim_end must be greater than trim_start.")


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
            "offset_x": j.offset_x,
            "offset_y": j.offset_y,
            "size": j.size,
            "start": j.start,
            "end": j.end,
        }
        for j in (jobs or [])
    ]
    crop_run_id, _run_path = emit_crop_run(output_dir=out_dir, jobs=jobs_summary)
    results: list[Path] = []
    jobs_to_run = jobs if jobs else [CropJob()]
    dry_run = bool((ffmpeg_opts or {}).get("dry_run", False))
    prefer_hevc_hw = bool((ffmpeg_opts or {}).get("prefer_hevc_hw", False))
    for vi, src in enumerate(input_videos):
        for ji, job in enumerate(jobs_to_run):
            _validate_job(job)
            spec = SquareCropSpec(
                size=job.size,
                center_x=job.center_x,
                center_y=job.center_y,
                offset_x=_normalize_offset(job.offset_x),
                offset_y=_normalize_offset(job.offset_y),
                start=job.start,
                end=job.end,
            )
            _plan = plan_crops([src], spec)
            for ti, (_src, _flt) in enumerate(_plan):
                out = out_dir / f"crop_{vi:03d}_job{ji:02d}_t{ti:02d}_s{spec.size}.mp4"
                result = run_square_crop(
                    src, out, spec, dry_run=dry_run, prefer_hevc_hw=prefer_hevc_hw
                )
                if dry_run:
                    # Touch file to simulate output for tests or dry-run workflows
                    out.write_bytes(b"")
                else:
                    # Emit per-view provenance
                    try:
                        crop_spec = {
                            "size": spec.size,
                            "size_px": spec.size,
                            "target_size_px": spec.size,
                            "center_x": spec.center_x,
                            "center_y": spec.center_y,
                            "offset_x": spec.offset_x,
                            "offset_y": spec.offset_y,
                            "start": spec.start if spec.start is not None else None,
                            "end": spec.end if spec.end is not None else None,
                            "trim_start_sec": spec.start if spec.start is not None else None,
                            "trim_end_sec": spec.end if spec.end is not None else None,
                            "trim_unit": "time"
                            if spec.start is not None or spec.end is not None
                            else None,
                            "offset_unit": "margin_relative"
                            if spec.offset_x is not None or spec.offset_y is not None
                            else None,
                        }
                        clean_crop_spec = {k: v for k, v in crop_spec.items() if v is not None}
                        emit_crop_view(
                            crop_run_id=crop_run_id,
                            source_path=src,
                            output_path=out,
                            crop_spec=clean_crop_spec,
                            encode_info={
                                "codec": result.encoder_used,
                                "hardware_attempted": result.encoder_attempted,
                                "hardware_used": None
                                if result.encoder_used == "libx264"
                                else result.encoder_used,
                            },
                            job_ref=f"job{ji}",
                        )
                    except Exception as e:
                        import logging

                        logging.getLogger(__name__).debug("crop provenance emission failed: %s", e)
                results.append(out)
    return results
