from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cosmos.sdk.crop import CropJob

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


def parse_jobs_json(path: Path) -> list[CropJob]:
    data = json.loads(Path(path).read_text())
    objs: list[dict[str, Any]]
    if isinstance(data, list):
        objs = data
    elif isinstance(data, dict):
        objs = [data]
    else:
        raise ValueError("Unsupported jobs JSON structure")

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
