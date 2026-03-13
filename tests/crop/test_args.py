from pathlib import Path

from cosmos.ffmpeg.args import (
    build_optimize_remux_args,
    build_optimize_transcode_args,
    build_square_crop_args,
)


def test_build_square_crop_args_with_times(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_square_crop_args(
        inp, out, encoder="libx264", crop_filter="crop=100:100:0:0", start=1.5, end=3.0
    )
    joined = " ".join(args)
    assert "-ss 1.5" in joined
    assert "-t 1.5" in joined
    assert "-vf crop=100:100:0:0" in joined
    assert str(out) in joined


def test_build_optimize_remux_args_faststart(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_optimize_remux_args(inp, out, faststart=True)
    joined = " ".join(args)
    assert "-map 0" in joined
    assert "-c copy" in joined
    assert "-movflags faststart" in joined
    assert str(out) in joined


def test_build_square_crop_args_bitexact(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_square_crop_args(
        inp, out, encoder="libx264", crop_filter="crop=100:100:0:0", bitexact=True
    )
    joined = " ".join(args)
    assert "-bitexact" in joined
    assert "+bitexact" in joined


def test_build_square_crop_args_threads_pinned(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_square_crop_args(
        inp, out, encoder="libx264", crop_filter="crop=100:100:0:0", threads=4
    )
    joined = " ".join(args)
    assert "-threads 4" in joined
    assert "threads=4" in joined


def test_build_square_crop_args_threads_ignored_non_x264(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_square_crop_args(
        inp, out, encoder="h264_nvenc", crop_filter="crop=100:100:0:0", threads=4
    )
    joined = " ".join(args)
    assert "-threads" not in joined


def test_build_optimize_remux_args_bitexact(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_optimize_remux_args(inp, out, faststart=True, bitexact=True)
    joined = " ".join(args)
    assert "-bitexact" in joined
    assert "+bitexact" in joined


def test_build_optimize_transcode_args_with_filters(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_optimize_transcode_args(
        inp,
        out,
        encoder="libx264",
        target_height=1080,
        fps=30.0,
        crf=23,
        faststart=True,
    )
    joined = " ".join(args)
    assert "-vf scale=-2:1080:flags=lanczos,fps=30" in joined
    assert "-c:v libx264" in joined
    assert "-crf 23" in joined
    assert "-c:a copy" in joined
    assert "-movflags faststart" in joined


def test_build_optimize_transcode_args_bitexact_and_threads(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    args = build_optimize_transcode_args(
        inp,
        out,
        encoder="libx264",
        target_height=None,
        fps=None,
        crf=None,
        faststart=False,
        threads=4,
        bitexact=True,
    )
    joined = " ".join(args)
    assert "-threads 4" in joined
    assert "-bitexact" in joined
    assert "+bitexact" in joined
