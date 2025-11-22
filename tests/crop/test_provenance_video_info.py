import shutil
from pathlib import Path
from subprocess import run

import pytest
from cosmos.sdk.provenance import ffprobe_video

ffmpeg_missing = shutil.which("ffmpeg") is None


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_ffprobe_video_fields(tmp_path: Path) -> None:
    src = tmp_path / "tiny.mp4"
    # Generate a 1s 320x240 5fps color test pattern
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x240:rate=5",
        "-t",
        "1",
        str(src),
    ]
    run(cmd, check=True, capture_output=True)  # noqa: S603
    info = ffprobe_video(src)
    assert info["width"] == 320
    assert info["height"] == 240
    assert info["width_px"] == 320
    assert info["height_px"] == 240
    assert info["fps"] == pytest.approx(5.0, rel=1e-2)
    assert info["duration_sec"] == pytest.approx(1.0, rel=1e-1)
