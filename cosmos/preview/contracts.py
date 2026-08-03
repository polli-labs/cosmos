from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from typus import BBoxXYWHNorm


class PreviewRect(BaseModel):
    """Authoritative ffmpeg rectangle plus its lossy normalized projection.

    The eight model fields are the frozen preview-plan v1 wire contract. Use
    :attr:`typus_bbox` for an optional canonical Typus view; it is derived and
    never serialized as a ninth source of truth.
    """

    x_px: int
    y_px: int
    w_px: int
    h_px: int
    x_norm: float
    y_norm: float
    w_norm: float
    h_norm: float

    @property
    def typus_bbox(self) -> BBoxXYWHNorm | None:
        """Return the canonical Typus bbox when the normalized view is representable.

        ``None`` means these known Cosmos coordinates cannot be represented by
        ``BBoxXYWHNorm``. That includes valid preview-plan v1 rectangles whose
        forced-even pixel extent normalizes to zero, and lossy rounded bounds
        rejected by Typus. No positive epsilon or adjusted bound is fabricated.
        """
        try:
            return BBoxXYWHNorm(
                x=self.x_norm,
                y=self.y_norm,
                w=self.w_norm,
                h=self.h_norm,
            )
        except ValueError:
            return None


class ResolvedFrame(BaseModel):
    selector: str
    time_sec: float
    warnings: list[str] = Field(default_factory=list)


class ViewPreview(BaseModel):
    view_id: str
    crop_mode: str
    crop_input: dict[str, Any]
    crop_px: PreviewRect
    trim_start_sec: float | None = None
    trim_end_sec: float | None = None
    frame_times: list[ResolvedFrame] = Field(default_factory=list)
    frame_times_sec: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    annotations: dict[str, Any] | None = None


class ClipArtifacts(BaseModel):
    plan: str
    frames: list[str] = Field(default_factory=list)
    sheets: list[str] = Field(default_factory=list)
    stacked: list[str] = Field(default_factory=list)


class ClipPreviewPlan(BaseModel):
    schema_version: str = Field(default="1.0.0")
    source: dict[str, Any]
    video: dict[str, Any]
    frame_selectors: list[str] = Field(default_factory=list)
    stack_times_sec: list[float] = Field(default_factory=list)
    resolved_frames: list[ResolvedFrame] = Field(default_factory=list)
    views: list[ViewPreview] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: ClipArtifacts


class CropPreviewRun(BaseModel):
    schema_version: str = Field(default="1.0.0")
    preview_run_id: str
    tool: str = Field(default="cosmos-crop-preview")
    version: str
    git: str | None = None
    time: str
    output_dir: str
    frame_selectors: list[str] = Field(default_factory=list)
    stack_times_sec: list[float] = Field(default_factory=list)
    render_defaults: dict[str, Any] = Field(default_factory=dict)
    ffmpeg: dict[str, Any] | None = None
    system: dict[str, Any] | None = None
    clips: list[ClipPreviewPlan] = Field(default_factory=list)
