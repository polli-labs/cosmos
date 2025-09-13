from pathlib import Path
from unittest.mock import patch

from cosmos.crop.squarecrop import SquareCropSpec, build_crop_filter, run_square_crop


def test_build_crop_filter_center():
    spec = SquareCropSpec(size=1080, center_x=0.5, center_y=0.5)
    flt = build_crop_filter(spec)
    assert flt.startswith("crop=1080:1080:")


def test_run_square_crop_builds_args(tmp_path: Path):
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"")
    out = tmp_path / "out.mp4"
    spec = SquareCropSpec(size=512, center_x=0.45, center_y=0.55)
    # Patch both the local run (which should not be called) and the detect one (may be called)
    with patch("cosmos.crop.squarecrop.subprocess.run") as mock_local_run, patch(
        "cosmos.ffmpeg.detect.subprocess.run"
    ) as _mock_detect_run:
        args = run_square_crop(inp, out, spec, dry_run=True)
        # In dry-run we should not actually spawn ffmpeg for execution
        assert not mock_local_run.called
        # The args should mention the crop filter and output
        assert "-vf" in args
        assert "crop=512:512:" in " ".join(args)
        assert str(out) in args
