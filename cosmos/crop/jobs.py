from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cosmos.sdk.crop import CropJob


def parse_jobs_json(path: Path) -> list[CropJob]:
    data = json.loads(Path(path).read_text())
    # If file is an object with job fields, use it; if it’s an array, map each
    objs: list[dict[str, Any]]
    if isinstance(data, list):
        objs = data
    elif isinstance(data, dict):
        objs = [data]
    else:
        raise ValueError("Unsupported jobs JSON structure")

    jobs: list[CropJob] = []
    for obj in objs:
        # Squarecrop-like schema support
        offset_x = float(obj.get("offset_x", 0.0))
        offset_y = float(obj.get("offset_y", 0.0))
        centers = (
            float(obj.get("center_x", 0.5)),
            float(obj.get("center_y", 0.5)),
        )
        center_x = centers[0] if "center_x" in obj else 0.5 + offset_x
        center_y = centers[1] if "center_y" in obj else 0.5 + offset_y

        # Targets: may be a single int or an array (square sizes)
        targets = obj.get("targets", obj.get("size", 1080))
        if isinstance(targets, int):
            targets_list = [targets]
        else:
            targets_list = list(targets)

        # Trims
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
        start_f = parse_time(start) if trim_unit == "time" else None
        end_f = parse_time(end) if trim_unit == "time" else None

        for size in targets_list:
            jobs.append(CropJob(center_x=center_x, center_y=center_y, size=int(size), start=start_f, end=end_f))
    return jobs

