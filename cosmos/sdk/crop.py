from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from cosmos.crop.rectcrop import RectCropSpec, build_rect_crop_filter, run_rect_crop
from cosmos.crop.squarecrop import SquareCropSpec, plan_crops, run_square_crop
from cosmos.sdk.provenance import emit_crop_run, emit_crop_view

logger = logging.getLogger(__name__)


@dataclass
class CropJob:
    center_x: float | None = None
    center_y: float | None = None
    offset_x: float | None = None
    offset_y: float | None = None
    size: int = 1080
    start: float | None = None
    end: float | None = None


@dataclass
class RectCropJob:
    """Rectangular crop job — used for general (non-square) crop regions."""

    x0: float = 0.0
    y0: float = 0.0
    w: float = 1.0
    h: float = 1.0
    normalized: bool = True
    start: float | None = None
    end: float | None = None
    view_id: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)


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


def _validate_rect_job(job: RectCropJob) -> None:
    if job.w <= 0 or job.h <= 0:
        raise ValueError("Invalid rect crop: width and height must be > 0.")
    for name, val in [("x0", job.x0), ("y0", job.y0), ("w", job.w), ("h", job.h)]:
        if val < 0:
            raise ValueError(f"Invalid rect crop: {name} must be non-negative (got {val}).")
    if job.normalized:
        if job.x0 + job.w > 1.0 + 1e-9:
            raise ValueError("Invalid rect crop: x0 + w must be <= 1.0 in normalized mode.")
        if job.y0 + job.h > 1.0 + 1e-9:
            raise ValueError("Invalid rect crop: y0 + h must be <= 1.0 in normalized mode.")
    if job.start is not None and job.end is not None and job.end <= job.start:
        raise ValueError("Invalid trim window: trim_end must be greater than trim_start.")


def crop(
    input_videos: list[Path],
    jobs: list[CropJob] | list[RectCropJob],
    out_dir: Path,
    *,
    ffmpeg_opts: dict[str, object] | None = None,
) -> list[Path]:
    """Return list of cropped video paths.

    Accepts either square CropJob list or rectangular RectCropJob list.

    ``ffmpeg_opts`` may include:
      - ``dry_run`` (bool)
      - ``prefer_hevc_hw`` (bool)
      - ``profile`` (str | None) – determinism profile name
    """
    from cosmos.sdk.profiles import resolve_profile

    out_dir.mkdir(parents=True, exist_ok=True)
    opts = ffmpeg_opts or {}
    dry_run = bool(opts.get("dry_run", False))
    prefer_hevc_hw = bool(opts.get("prefer_hevc_hw", False))

    # Resolve determinism profile for crop
    profile = resolve_profile(str(opts["profile"]) if opts.get("profile") else None)
    encoder_override = profile.pinned_encoder if profile else None
    threads = profile.threads if profile else None
    bitexact = profile.bitexact if profile else False

    if not jobs:
        return _crop_square(
            input_videos,
            [],
            out_dir,
            dry_run=dry_run,
            prefer_hevc_hw=prefer_hevc_hw,
            encoder_override=encoder_override,
            threads=threads,
            bitexact=bitexact,
        )

    # Detect crop mode from job types and enforce homogeneous lists.
    if all(isinstance(j, RectCropJob) for j in jobs):
        rect_jobs = [cast(RectCropJob, j) for j in jobs]
        return _crop_rect(
            input_videos,
            rect_jobs,
            out_dir,
            dry_run=dry_run,
            prefer_hevc_hw=prefer_hevc_hw,
            encoder_override=encoder_override,
            threads=threads,
            bitexact=bitexact,
        )

    if all(isinstance(j, CropJob) for j in jobs):
        square_jobs = [cast(CropJob, j) for j in jobs]
        return _crop_square(
            input_videos,
            square_jobs,
            out_dir,
            dry_run=dry_run,
            prefer_hevc_hw=prefer_hevc_hw,
            encoder_override=encoder_override,
            threads=threads,
            bitexact=bitexact,
        )

    raise ValueError("Jobs must be all CropJob or all RectCropJob.")


def _crop_rect(
    input_videos: list[Path],
    jobs: list[RectCropJob],
    out_dir: Path,
    *,
    dry_run: bool,
    prefer_hevc_hw: bool,
    encoder_override: str | None = None,
    threads: int | None = None,
    bitexact: bool = False,
) -> list[Path]:
    jobs_summary = [
        {
            "crop_mode": "rect",
            "x0": j.x0,
            "y0": j.y0,
            "w": j.w,
            "h": j.h,
            "normalized": j.normalized,
            "start": j.start,
            "end": j.end,
            "view_id": j.view_id,
        }
        for j in jobs
    ]
    crop_run_id, _run_path = emit_crop_run(output_dir=out_dir, jobs=jobs_summary)
    results: list[Path] = []
    for vi, src in enumerate(input_videos):
        for ji, job in enumerate(jobs):
            _validate_rect_job(job)
            spec = RectCropSpec(
                x0=job.x0,
                y0=job.y0,
                w=job.w,
                h=job.h,
                normalized=job.normalized,
                start=job.start,
                end=job.end,
            )
            out_name = f"{job.view_id}.mp4" if job.view_id else f"crop_{vi:03d}_rect{ji:02d}.mp4"
            out = out_dir / out_name
            result = run_rect_crop(
                src,
                out,
                spec,
                dry_run=dry_run,
                prefer_hevc_hw=prefer_hevc_hw,
                encoder_override=encoder_override,
                threads=threads,
                bitexact=bitexact,
            )
            if dry_run:
                out.write_bytes(b"")
            else:
                try:
                    # Build provenance with both normalized and pixel coords
                    from cosmos.ffmpeg.detect import _probe_dimensions

                    probed_w, probed_h = _probe_dimensions(src)
                    source_w = probed_w or 0
                    source_h = probed_h or 0
                    crop_filter = build_rect_crop_filter(spec, source_w, source_h)
                    filter_parts = crop_filter.replace("crop=", "").split(":")
                    px_w, px_h, px_x, px_y = (int(p) for p in filter_parts)
                    crop_spec: dict[str, Any] = {
                        "crop_mode": "rect",
                        "x0_norm": job.x0 if job.normalized else None,
                        "y0_norm": job.y0 if job.normalized else None,
                        "w_norm": job.w if job.normalized else None,
                        "h_norm": job.h if job.normalized else None,
                        "x_px": px_x,
                        "y_px": px_y,
                        "w_px": px_w,
                        "h_px": px_h,
                        "source_w_px": source_w,
                        "source_h_px": source_h,
                        "view_id": job.view_id,
                        "annotations": job.annotations if job.annotations else None,
                        "trim_start_sec": spec.start,
                        "trim_end_sec": spec.end,
                        "trim_unit": "time"
                        if spec.start is not None or spec.end is not None
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
                        job_ref=job.view_id or f"rect{ji}",
                    )
                except Exception as e:
                    logger.debug("crop provenance emission failed: %s", e)
            results.append(out)
    return results


def _crop_square(
    input_videos: list[Path],
    jobs: list[CropJob],
    out_dir: Path,
    *,
    dry_run: bool,
    prefer_hevc_hw: bool,
    encoder_override: str | None = None,
    threads: int | None = None,
    bitexact: bool = False,
) -> list[Path]:
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
                    src,
                    out,
                    spec,
                    dry_run=dry_run,
                    prefer_hevc_hw=prefer_hevc_hw,
                    encoder_override=encoder_override,
                    threads=threads,
                    bitexact=bitexact,
                )
                if dry_run:
                    out.write_bytes(b"")
                else:
                    try:
                        crop_spec: dict[str, Any] = {
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
                        logger.debug("crop provenance emission failed: %s", e)
                results.append(out)
    return results
