from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PreviewRect(BaseModel):
    x_px: int
    y_px: int
    w_px: int
    h_px: int
    x_norm: float
    y_norm: float
    w_norm: float
    h_norm: float


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
