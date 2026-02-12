from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from cosmos.sdk.crop import RectCropJob

logger = logging.getLogger(__name__)

# Default pattern: {date}/8k/{clip}.mp4  (date = Apr25-style short name)
DEFAULT_CLIP_PATTERN = "{date}/8k/{clip}.mp4"


def _iso_date_to_fs(iso_date: str) -> str:
    """Convert ISO date (2025-04-25) to filesystem format (Apr25).

    Parses with datetime and formats as %b%d (abbreviated month + zero-padded day).
    """
    dt = datetime.strptime(iso_date, "%Y-%m-%d")  # noqa: DTZ007
    return dt.strftime("%b%d")


def parse_curated_views(
    spec_path: str | Path,
    source_root: str | Path,
    *,
    clip_pattern: str = DEFAULT_CLIP_PATTERN,
) -> list[tuple[Path, RectCropJob]]:
    """Parse a curated-views-spec JSON and return (source_path, RectCropJob) pairs.

    Each view in the spec maps to one RectCropJob with its source video path resolved
    under *source_root* using *clip_pattern*.

    Raises FileNotFoundError if a resolved source clip does not exist.
    Logs a warning for views with ``preprocess.color_correction`` (deferred feature).
    """
    spec_path = Path(spec_path)
    source_root = Path(source_root)

    data: dict[str, Any] = json.loads(spec_path.read_text())
    views: list[dict[str, Any]] = data.get("views", [])

    result: list[tuple[Path, RectCropJob]] = []

    for view in views:
        view_id: str = view["id"]
        source_info: dict[str, Any] = view["source"]
        clip_name: str = source_info["clip"]
        iso_date: str = source_info["date"]

        # Map ISO date -> filesystem date format
        fs_date = _iso_date_to_fs(iso_date)

        # Resolve source path
        rel = clip_pattern.format(date=fs_date, clip=clip_name)
        source_path = source_root / rel
        if not source_path.exists():
            raise FileNotFoundError(
                f"Source clip not found: {source_path} (view={view_id}, clip={clip_name}, date={iso_date})"
            )

        # Parse crop_norm
        crop_norm: dict[str, float] = view["crop_norm"]
        x0 = float(crop_norm["x0"])
        y0 = float(crop_norm["y0"])
        w = float(crop_norm["w"])
        h = float(crop_norm["h"])

        # Parse trim
        trim: dict[str, Any] = view.get("trim", {})
        start_s: float | None = trim.get("start_s")
        end_s: float | None = trim.get("end_s")

        # Annotations
        annotations: dict[str, Any] = view.get("annotations", {})

        # Warn about deferred color_correction
        preprocess = view.get("preprocess", {})
        if preprocess.get("color_correction"):
            logger.warning(
                "View %s has preprocess.color_correction: %r — not yet implemented; skipping color correction",
                view_id,
                preprocess["color_correction"],
            )

        job = RectCropJob(
            x0=x0,
            y0=y0,
            w=w,
            h=h,
            normalized=True,
            start=start_s,
            end=end_s,
            view_id=view_id,
            annotations=annotations,
        )
        result.append((source_path, job))

    return result
