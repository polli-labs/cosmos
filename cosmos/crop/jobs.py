from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cosmos.sdk.crop import CropJob, RectCropJob

RANGE_MSG = "offset must be between -1 and 1"


def _check_offset(val: Any | None) -> float | None:
    if val is None:
        return None
    f = float(val)
    if f < -1.0 or f > 1.0:
        raise ValueError(f"{RANGE_MSG} (got {f})")
    return f


def _parse_targets(obj: dict[str, Any]) -> list[int]:
    targets = obj.get("targets", obj.get("size", 1080))
    if isinstance(targets, int):
        return [targets]
    return [int(t) for t in targets]


def _parse_trim(obj: dict[str, Any]) -> tuple[float | None, float | None]:
    trim_unit = obj.get("trim_unit", "time")
    start = obj.get("trim_start")
    end = obj.get("trim_end")

    def parse_time(v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    if trim_unit != "time":
        return None, None
    return parse_time(start), parse_time(end)


def _parse_rect_crop(obj: dict[str, Any]) -> tuple[float, float, float, float, bool]:
    """Parse rect crop coords from ``crop_norm`` (4 floats) or ``crop_px`` (4 ints).

    Returns (x0, y0, w, h, normalized).
    """
    if "crop_norm" in obj and "crop_px" in obj:
        raise ValueError("Provide exactly one of crop_norm or crop_px")
    if "crop_norm" in obj:
        cn = obj["crop_norm"]
        if isinstance(cn, list | tuple):
            x0, y0, w, h = (float(v) for v in cn)
        elif isinstance(cn, dict):
            x0 = float(cn["x0"])
            y0 = float(cn["y0"])
            w = float(cn["w"])
            h = float(cn["h"])
        else:
            raise ValueError(f"crop_norm must be list or dict, got {type(cn).__name__}")
        return x0, y0, w, h, True
    if "crop_px" in obj:
        cp = obj["crop_px"]
        if isinstance(cp, list | tuple):
            x0, y0, w, h = (int(v) for v in cp)
        elif isinstance(cp, dict):
            x0 = int(cp["x0"])
            y0 = int(cp["y0"])
            w = int(cp["w"])
            h = int(cp["h"])
        else:
            raise ValueError(f"crop_px must be list or dict, got {type(cp).__name__}")
        return float(x0), float(y0), float(w), float(h), False
    raise ValueError("rect crop_mode requires crop_norm or crop_px")


def _validate_rect_norm(x0: float, y0: float, w: float, h: float) -> None:
    """Validate that normalized rect coords are within [0,1] bounds."""
    for name, val in [("x0", x0), ("y0", y0), ("w", w), ("h", h)]:
        if val < 0:
            raise ValueError(f"rect coord {name} must be non-negative (got {val})")
    if x0 + w > 1.0 + 1e-9:
        raise ValueError(f"x0 + w exceeds 1.0 ({x0} + {w} = {x0 + w})")
    if y0 + h > 1.0 + 1e-9:
        raise ValueError(f"y0 + h exceeds 1.0 ({y0} + {h} = {y0 + h})")


def _validate_rect_px(x0: float, y0: float, w: float, h: float) -> None:
    """Validate that pixel rect coords are non-negative."""
    for name, val in [("x0", x0), ("y0", y0), ("w", w), ("h", h)]:
        if val < 0:
            raise ValueError(f"rect coord {name} must be non-negative (got {val})")


def parse_jobs_json(path: Path) -> list[CropJob] | list[RectCropJob]:
    """Parse a jobs JSON file.

    Returns square CropJob list by default. When ``crop_mode == "rect"``
    is present, returns RectCropJob list instead.
    """
    data = json.loads(Path(path).read_text())
    objs: list[dict[str, Any]]
    if isinstance(data, list):
        objs = data
    elif isinstance(data, dict):
        objs = [data]
    else:
        raise ValueError("Unsupported jobs JSON structure")

    # Detect crop mode from first object (all must be consistent)
    crop_mode = objs[0].get("crop_mode", "square") if objs else "square"

    if crop_mode == "rect":
        return _parse_rect_jobs(objs)
    return _parse_square_jobs(objs)


def _parse_rect_jobs(objs: list[dict[str, Any]]) -> list[RectCropJob]:
    jobs: list[RectCropJob] = []
    for obj in objs:
        x0, y0, w, h, normalized = _parse_rect_crop(obj)
        if normalized:
            _validate_rect_norm(x0, y0, w, h)
        else:
            _validate_rect_px(x0, y0, w, h)
        start_f, end_f = _parse_trim(obj)
        view_id = obj.get("view_id") or obj.get("id")
        annotations = obj.get("annotations", {})
        jobs.append(
            RectCropJob(
                x0=x0,
                y0=y0,
                w=w,
                h=h,
                normalized=normalized,
                start=start_f,
                end=end_f,
                view_id=view_id,
                annotations=annotations if isinstance(annotations, dict) else {},
            )
        )
    return jobs


def _parse_square_jobs(objs: list[dict[str, Any]]) -> list[CropJob]:
    jobs: list[CropJob] = []
    for obj in objs:
        has_offsets = ("offset_x" in obj) or ("offset_y" in obj)
        has_centers = ("center_x" in obj) or ("center_y" in obj)
        if has_offsets and has_centers:
            raise ValueError(
                "Provide either offsets or centers, not both (offsets are margin-relative in [-1,1])"
            )
        start_f, end_f = _parse_trim(obj)
        offset_x = _check_offset(obj.get("offset_x"))
        offset_y = _check_offset(obj.get("offset_y"))
        center_x = obj.get("center_x")
        center_y = obj.get("center_y")
        for size in _parse_targets(obj):
            jobs.append(
                CropJob(
                    center_x=(float(center_x) if center_x is not None else None),
                    center_y=(float(center_y) if center_y is not None else None),
                    offset_x=offset_x,
                    offset_y=offset_y,
                    size=int(size),
                    start=start_f,
                    end=end_f,
                )
            )
    return jobs
