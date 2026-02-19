from __future__ import annotations

from cosmos.crop.rectcrop import RectCropSpec, build_rect_crop_filter
from cosmos.preview.planner import (
    _parse_rect_filter,
    build_view_preview,
    compute_rect_geometry,
    compute_square_geometry,
)
from cosmos.sdk.crop import CropJob, RectCropJob


def test_compute_rect_geometry_reports_even_rounding() -> None:
    job = RectCropJob(x0=0.0, y0=0.0, w=0.333, h=0.333, normalized=True)
    rect, warnings = compute_rect_geometry(job, source_w=1920, source_h=1080)

    assert rect.w_px == 638
    assert rect.h_px == 358
    assert any("rounded down to even" in warning for warning in warnings)


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
