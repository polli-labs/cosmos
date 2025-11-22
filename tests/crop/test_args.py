from pathlib import Path

from cosmos.ffmpeg.args import build_square_crop_args


def test_build_square_crop_args_with_times(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_square_crop_args(
        inp, out, encoder="libx264", crop_filter="crop=100:100:0:0", start=1.5, end=3.0
    )
    joined = " ".join(args)
    assert "-ss 1.5" in joined
    assert "-to 3.0" in joined
    assert "-vf crop=100:100:0:0" in joined
    assert str(out) in joined
