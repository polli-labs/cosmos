from __future__ import annotations

import json
from pathlib import Path

import pytest
from cosmos.crop.rectcrop import RectCropSpec, build_rect_crop_filter
from cosmos.preview.contracts import PreviewRect
from cosmos.preview.planner import (
    _parse_rect_filter,
    build_view_preview,
    compute_rect_geometry,
    compute_square_geometry,
)
from cosmos.sdk.crop import CropJob, RectCropJob
from typus import BBoxXYWHNorm, to_xyxy_px


def test_compute_rect_geometry_reports_even_rounding() -> None:
    job = RectCropJob(x0=0.0, y0=0.0, w=0.333, h=0.333, normalized=True)
    rect, warnings = compute_rect_geometry(job, source_w=1920, source_h=1080)

    assert rect.w_px == 638
    assert rect.h_px == 358
    assert any("rounded down to even" in warning for warning in warnings)
    assert rect.typus_bbox == BBoxXYWHNorm(
        x=0.0,
        y=0.0,
        w=0.332292,
        h=0.331481,
    )


def test_preview_rect_schema_v1_bytes_and_fields_remain_frozen() -> None:
    rect = PreviewRect(
        x_px=192,
        y_px=216,
        w_px=638,
        h_px=478,
        x_norm=0.1,
        y_norm=0.2,
        w_norm=0.332292,
        h_norm=0.442593,
    )
    fixture = Path(__file__).parent / "fixtures" / "preview_rect_schema_v1.json"
    serialized = (rect.model_dump_json() + "\n").encode()

    assert serialized == fixture.read_bytes()
    assert list(json.loads(serialized)) == [
        "x_px",
        "y_px",
        "w_px",
        "h_px",
        "x_norm",
        "y_norm",
        "w_norm",
        "h_norm",
    ]
    assert tuple(PreviewRect.model_fields) == (
        "x_px",
        "y_px",
        "w_px",
        "h_px",
        "x_norm",
        "y_norm",
        "w_norm",
        "h_norm",
    )
    assert "typus_bbox" not in rect.model_dump()


def test_typus_view_uses_ffmpeg_truncation_truth_not_input_rounding() -> None:
    job = RectCropJob(
        x0=0.00075,
        y0=0.00075,
        w=0.01075,
        h=0.01075,
        normalized=True,
    )
    rect, _warnings = compute_rect_geometry(job, source_w=1000, source_h=1000)
    input_bbox = BBoxXYWHNorm(x=job.x0, y=job.y0, w=job.w, h=job.h)

    assert to_xyxy_px(input_bbox, 1000, 1000) == (1, 1, 12, 12)
    assert (rect.x_px, rect.y_px, rect.w_px, rect.h_px) == (0, 0, 10, 10)
    assert rect.typus_bbox is not None
    assert to_xyxy_px(rect.typus_bbox, 1000, 1000) == (0, 0, 10, 10)


def test_typus_view_uses_post_clamp_pixel_truth() -> None:
    job = RectCropJob(x0=900, y0=900, w=500, h=500, normalized=False)
    rect, warnings = compute_rect_geometry(job, source_w=1000, source_h=1000)

    assert (rect.x_px, rect.y_px, rect.w_px, rect.h_px) == (900, 900, 100, 100)
    assert rect.typus_bbox == BBoxXYWHNorm(x=0.9, y=0.9, w=0.1, h=0.1)
    assert "crop width was clamped to frame bounds" in warnings
    assert "crop height was clamped to frame bounds" in warnings


def test_typus_view_is_none_for_zero_normalized_extent_without_fabrication() -> None:
    job = RectCropJob(x0=10, y0=20, w=1, h=2, normalized=False)
    rect, warnings = compute_rect_geometry(job, source_w=1000, source_h=1000)

    assert rect.w_px == 0
    assert rect.w_norm == 0.0
    assert rect.typus_bbox is None
    assert "w_px rounded down to even" in warnings


def test_typus_view_is_none_when_lossy_boundary_rounding_exceeds_bounds() -> None:
    rect, _warnings = compute_rect_geometry(
        RectCropJob(x0=18, y0=0, w=1262, h=2, normalized=False),
        source_w=1280,
        source_h=2,
    )

    assert rect.x_px + rect.w_px == 1280
    assert rect.x_norm + rect.w_norm == pytest.approx(1.000001)
    assert rect.typus_bbox is None


def test_parse_rect_filter_round_trip_with_crop_builder() -> None:
    spec = RectCropSpec(x0=0.1, y0=0.2, w=0.333, h=0.444, normalized=True)
    filter_string = build_rect_crop_filter(spec, 1920, 1080)
    assert filter_string == "crop=638:478:192:216"

    x_px, y_px, w_px, h_px = _parse_rect_filter(filter_string)
    assert (x_px, y_px, w_px, h_px) == (192, 216, 638, 478)


def test_compute_square_geometry_clamps_out_of_bounds_center() -> None:
    job = CropJob(center_x=1.5, center_y=-0.2, size=400)
    rect, warnings = compute_square_geometry(job, source_w=1000, source_h=800)

    assert rect.x_px == 600
    assert rect.y_px == 0
    assert rect.w_px == 400
    assert rect.h_px == 400
    assert any("center_x" in warning for warning in warnings)
    assert any("center_y" in warning for warning in warnings)


def test_build_view_preview_resolves_selector_times() -> None:
    job = RectCropJob(
        x0=0.1,
        y0=0.1,
        w=0.4,
        h=0.3,
        normalized=True,
        start=2.0,
        end=12.0,
        view_id="v1",
    )
    view = build_view_preview(
        job=job,
        index=0,
        source_w=2000,
        source_h=1000,
        duration_sec=30.0,
        frame_selectors=["start", "mid", "end"],
    )

    assert view.view_id == "v1"
    assert view.frame_times_sec == [2.0, 7.0, 12.0]
