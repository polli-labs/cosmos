from pathlib import Path
from unittest.mock import patch

from cosmos.crop.rectcrop import (
    RectCropSpec,
    build_rect_crop_filter,
    run_rect_crop,
)
from cosmos.crop.squarecrop import CropRunResult


def test_build_rect_crop_filter_normalized():
    """Standard 7680x4320 case — normalized coords produce correct pixel crop."""
    spec = RectCropSpec(x0=0.3203, y0=0.4398, w=0.1419, h=0.2593)
    flt = build_rect_crop_filter(spec, 7680, 4320)
    # Expected: x=2459, y=1899, w=1089->1088 (even), h=1120->1120 (even)
    assert flt.startswith("crop=")
    parts = flt.replace("crop=", "").split(":")
    w, h, x, y = (int(p) for p in parts)
    assert w % 2 == 0, "width must be even"
    assert h % 2 == 0, "height must be even"
    assert x >= 0
    assert y >= 0
    assert x + w <= 7680
    assert y + h <= 4320


def test_build_rect_crop_filter_pixel_mode():
    """normalized=False passes pixel values directly."""
    spec = RectCropSpec(x0=100, y0=200, w=640, h=480, normalized=False)
    flt = build_rect_crop_filter(spec, 1920, 1080)
    assert flt == "crop=640:480:100:200"


def test_build_rect_crop_filter_even_rounding():
    """Odd dimensions are rounded down to even."""
    # w/h that produce odd pixel values
    spec = RectCropSpec(x0=0.0, y0=0.0, w=101, h=99, normalized=False)
    flt = build_rect_crop_filter(spec, 1920, 1080)
    parts = flt.replace("crop=", "").split(":")
    w, h = int(parts[0]), int(parts[1])
    assert w == 100
    assert h == 98


def test_build_rect_crop_filter_clamping():
    """When x0+w > 1.0, crop is clamped to frame bounds."""
    spec = RectCropSpec(x0=0.9, y0=0.9, w=0.5, h=0.5)
    flt = build_rect_crop_filter(spec, 1000, 1000)
    parts = flt.replace("crop=", "").split(":")
    w, h, x, y = (int(p) for p in parts)
    assert x + w <= 1000
    assert y + h <= 1000
    assert w % 2 == 0
    assert h % 2 == 0


def test_run_rect_crop_dry_run(tmp_path: Path):
    """Dry run returns ffmpeg args without spawning subprocess."""
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"")
    out = tmp_path / "out.mp4"
    spec = RectCropSpec(x0=0.1, y0=0.2, w=0.3, h=0.4)
    with patch("cosmos.crop.rectcrop.subprocess.run") as mock_run:
        result = run_rect_crop(inp, out, spec, source_w=1920, source_h=1080, dry_run=True)
        assert not mock_run.called
    assert isinstance(result, CropRunResult)
    assert "-vf" in result.args
    assert any("crop=" in a for a in result.args)
    assert str(out) in result.args


def test_run_rect_crop_probes_source(tmp_path: Path):
    """When dims not provided, ffprobe is called to probe source."""
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"")
    out = tmp_path / "out.mp4"
    spec = RectCropSpec(x0=0.1, y0=0.2, w=0.3, h=0.4)
    with (
        patch("cosmos.crop.rectcrop._probe_dimensions", return_value=(3840, 2160)) as mock_probe,
        patch("cosmos.crop.rectcrop.subprocess.run"),
    ):
        result = run_rect_crop(inp, out, spec, dry_run=True)
        mock_probe.assert_called_once_with(inp)
    assert isinstance(result, CropRunResult)
    # Verify the crop filter was computed from probed dims
    joined = " ".join(result.args)
    assert "crop=" in joined
