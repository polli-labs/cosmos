from __future__ import annotations

from pathlib import Path

from cosmos.preview.pipeline import (
    PreviewRunResult,
    RenderOptions,
    generate_preview_for_curated_pairs,
    generate_preview_for_jobs,
)
from cosmos.sdk.crop import CropJob, RectCropJob


def preview(
    input_videos: list[Path],
    jobs: list[CropJob] | list[RectCropJob],
    out_dir: Path,
    *,
    options: RenderOptions,
) -> PreviewRunResult:
    return generate_preview_for_jobs(
        input_videos=input_videos,
        jobs=jobs,
        out_dir=out_dir,
        options=options,
    )


def preview_curated_views(
    pairs: list[tuple[Path, RectCropJob]],
    out_dir: Path,
    *,
    options: RenderOptions,
) -> PreviewRunResult:
    return generate_preview_for_curated_pairs(
        pairs=pairs,
        out_dir=out_dir,
        options=options,
    )


__all__ = [
    "RenderOptions",
    "PreviewRunResult",
    "preview",
    "preview_curated_views",
]
