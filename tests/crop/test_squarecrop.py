import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from cosmos.crop.squarecrop import CropRunResult, SquareCropSpec, build_crop_filter, run_square_crop

ffmpeg_missing = shutil.which("ffmpeg") is None


def test_build_crop_filter_center():
    spec = SquareCropSpec(size=1080, center_x=0.5, center_y=0.5)
    flt = build_crop_filter(spec)
    assert flt.startswith("crop=1080:1080:")


def test_run_square_crop_builds_args(tmp_path: Path):
    if ffmpeg_missing:
        pytest.skip("ffmpeg not available")
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"")
    out = tmp_path / "out.mp4"
    spec = SquareCropSpec(size=512, center_x=0.45, center_y=0.55)
    # Patch both the local run (which should not be called) and the detect one (may be called)
    with (
        patch("cosmos.crop.squarecrop.subprocess.run") as mock_local_run,
        patch("cosmos.ffmpeg.detect.subprocess.run") as _mock_detect_run,
    ):
        result = run_square_crop(inp, out, spec, dry_run=True)
        # In dry-run we should not actually spawn ffmpeg for execution
        assert not mock_local_run.called
        # The args should mention the crop filter and output
        assert "-vf" in result.args
        assert "crop=512:512:" in " ".join(result.args)
        assert str(out) in result.args
        assert isinstance(result, CropRunResult)


def test_build_crop_filter_offsets():
    spec = SquareCropSpec(size=640, offset_x=0.5, offset_y=-0.25)
    flt = build_crop_filter(spec)
    assert "crop=640:640:" in flt
    # Offsets should be present in expression
    assert "(iw-640)/2 + (0.5) * (iw-640)/2" in flt
    assert "(ih-640)/2 + (-0.25) * (ih-640)/2" in flt


def test_offset_bounds_expressions():
    spec_left = SquareCropSpec(size=100, offset_x=-1.0, offset_y=0)
    spec_right = SquareCropSpec(size=100, offset_x=1.0, offset_y=0)
    flt_left = build_crop_filter(spec_left)
    flt_right = build_crop_filter(spec_right)
    assert "(-1.0)" in flt_left
    assert "(1.0)" in flt_right
    iw = 200
    size = 100

    def margin_offset(offset: float) -> float:
        return (iw - size) / 2 + offset * (iw - size) / 2

    assert margin_offset(-1.0) == 0  # flush left
    assert margin_offset(1.0) == iw - size  # flush right


def test_offsets_and_centers_mutually_exclusive():
    job = SquareCropSpec(size=100, offset_x=0.2, center_x=0.3)
    flt = build_crop_filter(job)
    # offsets take precedence because centers are ignored when offsets present in filter builder
    assert "(0.2)" in flt


def test_hardware_fallback_to_software(tmp_path: Path, monkeypatch) -> None:
    if ffmpeg_missing:
        pytest.skip("ffmpeg not available")
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"video")
    out = tmp_path / "out.mp4"
    spec = SquareCropSpec(size=128, center_x=0.5, center_y=0.5)

    calls = []

    def fake_run(cmd, check, capture_output, text):  # noqa: ANN001
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(187, cmd, "fail")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("cosmos.crop.squarecrop.subprocess.run", fake_run)
    monkeypatch.setattr("cosmos.crop.squarecrop.choose_encoder", lambda: "h264_videotoolbox")
    result = run_square_crop(inp, out, spec, dry_run=False)
    assert result.encoder_attempted == "h264_videotoolbox"
    assert result.encoder_used == "libx264"
    assert len(calls) == 2
