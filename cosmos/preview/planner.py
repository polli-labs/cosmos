from __future__ import annotations

from typing import Any

from cosmos.crop.rectcrop import RectCropSpec, build_rect_crop_filter
from cosmos.preview.contracts import PreviewRect, ResolvedFrame, ViewPreview
from cosmos.preview.selectors import parse_frame_selector, resolve_frame_selector
from cosmos.sdk.crop import CropJob, RectCropJob


def _safe_norm(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 6)


def _parse_rect_filter(flt: str) -> tuple[int, int, int, int]:
    parts = flt.replace("crop=", "").split(":")
    if len(parts) != 4:
        raise ValueError(f"unexpected rect crop filter shape: {flt}")
    w_px, h_px, x_px, y_px = (int(part) for part in parts)
    return x_px, y_px, w_px, h_px


def compute_rect_geometry(
    job: RectCropJob,
    *,
    source_w: int,
    source_h: int,
) -> tuple[PreviewRect, list[str]]:
    warnings: list[str] = []

    if job.normalized:
        raw_x = int(job.x0 * source_w)
        raw_y = int(job.y0 * source_h)
        raw_w = int(job.w * source_w)
        raw_h = int(job.h * source_h)
    else:
        raw_x = int(job.x0)
        raw_y = int(job.y0)
        raw_w = int(job.w)
        raw_h = int(job.h)

    spec = RectCropSpec(
        x0=job.x0,
        y0=job.y0,
        w=job.w,
        h=job.h,
        normalized=job.normalized,
        start=job.start,
        end=job.end,
    )
    filter_string = build_rect_crop_filter(spec, source_w, source_h)
    x_px, y_px, w_px, h_px = _parse_rect_filter(filter_string)

    if raw_x + raw_w > source_w:
        warnings.append("crop width was clamped to frame bounds")
    if raw_y + raw_h > source_h:
        warnings.append("crop height was clamped to frame bounds")
    if raw_x < 0:
        warnings.append("crop x0 was clamped to 0")
    if raw_y < 0:
        warnings.append("crop y0 was clamped to 0")
    if raw_w % 2 != 0 and w_px != raw_w:
        warnings.append("w_px rounded down to even")
    if raw_h % 2 != 0 and h_px != raw_h:
        warnings.append("h_px rounded down to even")

    rect = PreviewRect(
        x_px=x_px,
        y_px=y_px,
        w_px=w_px,
        h_px=h_px,
        x_norm=_safe_norm(x_px, source_w),
        y_norm=_safe_norm(y_px, source_h),
        w_norm=_safe_norm(w_px, source_w),
        h_norm=_safe_norm(h_px, source_h),
    )
    return rect, warnings


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_square_geometry(
    job: CropJob,
    *,
    source_w: int,
    source_h: int,
) -> tuple[PreviewRect, list[str]]:
    warnings: list[str] = []
    size = int(job.size)
    if size <= 0:
        raise ValueError("square preview size must be positive")

    if size > source_w or size > source_h:
        new_size = min(source_w, source_h)
        warnings.append(f"square size {size}px exceeded frame bounds; clamped to {new_size}px")
        size = new_size

    if job.offset_x is not None or job.offset_y is not None:
        ox = job.offset_x if job.offset_x is not None else 0.0
        oy = job.offset_y if job.offset_y is not None else 0.0
        if ox < -1.0 or ox > 1.0:
            warnings.append("offset_x outside [-1,1] was clamped")
            ox = _clamp(ox, -1.0, 1.0)
        if oy < -1.0 or oy > 1.0:
            warnings.append("offset_y outside [-1,1] was clamped")
            oy = _clamp(oy, -1.0, 1.0)
        x_float = (source_w - size) / 2.0 + ox * ((source_w - size) / 2.0)
        y_float = (source_h - size) / 2.0 + oy * ((source_h - size) / 2.0)
    else:
        cx = job.center_x if job.center_x is not None else 0.5
        cy = job.center_y if job.center_y is not None else 0.5
        if cx < 0.0 or cx > 1.0:
            warnings.append("center_x outside [0,1] was clamped")
            cx = _clamp(cx, 0.0, 1.0)
        if cy < 0.0 or cy > 1.0:
            warnings.append("center_y outside [0,1] was clamped")
            cy = _clamp(cy, 0.0, 1.0)
        x_float = source_w * cx - size / 2.0
        y_float = source_h * cy - size / 2.0

    x_px = int(x_float)
    y_px = int(y_float)

    max_x = max(source_w - size, 0)
    max_y = max(source_h - size, 0)
    clamped_x = int(_clamp(float(x_px), 0.0, float(max_x)))
    clamped_y = int(_clamp(float(y_px), 0.0, float(max_y)))
    if clamped_x != x_px:
        warnings.append("square x coordinate was clamped to frame bounds")
    if clamped_y != y_px:
        warnings.append("square y coordinate was clamped to frame bounds")

    rect = PreviewRect(
        x_px=clamped_x,
        y_px=clamped_y,
        w_px=size,
        h_px=size,
        x_norm=_safe_norm(clamped_x, source_w),
        y_norm=_safe_norm(clamped_y, source_h),
        w_norm=_safe_norm(size, source_w),
        h_norm=_safe_norm(size, source_h),
    )
    return rect, warnings


def _resolve_view_frames(
    *,
    frame_selectors: list[str],
    duration_sec: float,
    trim_start_sec: float | None,
    trim_end_sec: float | None,
) -> tuple[list[ResolvedFrame], list[str]]:
    resolved: list[ResolvedFrame] = []
    warnings: list[str] = []

    for raw in frame_selectors:
        selector = parse_frame_selector(raw)
        resolved_time, selector_warnings = resolve_frame_selector(
            selector,
            duration_sec=duration_sec,
            trim_start_sec=trim_start_sec,
            trim_end_sec=trim_end_sec,
        )
        rounded_time = round(resolved_time, 3)
        frame = ResolvedFrame(selector=raw, time_sec=rounded_time, warnings=selector_warnings)
        resolved.append(frame)
        warnings.extend(selector_warnings)

    return resolved, warnings


def _view_id_for_job(job: CropJob | RectCropJob, *, index: int) -> str:
    if isinstance(job, RectCropJob):
        return job.view_id or f"view_{index:03d}"
    return f"square_{index:03d}"


def build_view_preview(
    *,
    job: CropJob | RectCropJob,
    index: int,
    source_w: int,
    source_h: int,
    duration_sec: float,
    frame_selectors: list[str],
) -> ViewPreview:
    trim_start = job.start
    trim_end = job.end

    if isinstance(job, RectCropJob):
        crop_mode = "rect"
        crop_px, geometry_warnings = compute_rect_geometry(
            job, source_w=source_w, source_h=source_h
        )
        crop_input: dict[str, Any] = {
            "x0": job.x0,
            "y0": job.y0,
            "w": job.w,
            "h": job.h,
            "normalized": job.normalized,
            "trim_start_sec": job.start,
            "trim_end_sec": job.end,
        }
        annotations = job.annotations if job.annotations else None
    else:
        crop_mode = "square"
        crop_px, geometry_warnings = compute_square_geometry(
            job, source_w=source_w, source_h=source_h
        )
        crop_input = {
            "size": job.size,
            "offset_x": job.offset_x,
            "offset_y": job.offset_y,
            "center_x": job.center_x,
            "center_y": job.center_y,
            "trim_start_sec": job.start,
            "trim_end_sec": job.end,
        }
        annotations = None

    frame_times, frame_warnings = _resolve_view_frames(
        frame_selectors=frame_selectors,
        duration_sec=duration_sec,
        trim_start_sec=trim_start,
        trim_end_sec=trim_end,
    )

    warnings = [*geometry_warnings, *frame_warnings]
    return ViewPreview(
        view_id=_view_id_for_job(job, index=index),
        crop_mode=crop_mode,
        crop_input={k: v for k, v in crop_input.items() if v is not None},
        crop_px=crop_px,
        trim_start_sec=trim_start,
        trim_end_sec=trim_end,
        frame_times=frame_times,
        frame_times_sec=[f.time_sec for f in frame_times],
        warnings=warnings,
        annotations=annotations,
    )
