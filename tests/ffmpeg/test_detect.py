import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available on PATH", allow_module_level=True)

from cosmos.ffmpeg.detect import choose_encoder, choose_encoder_for_video


def test_choose_encoder_prefers_nvenc_linux():
    text = "Encoders:\n V..... libx264 x264\n V..... h264_nvenc NVIDIA NVENC H.264 encoder\n V..... h264_vaapi H.264 VAAPI encoder\n"
    with patch("subprocess.run") as mock_run, patch("platform.system", return_value="Linux"):
        mock_run.return_value.stdout = text
        mock_run.return_value.stderr = ""
        enc = choose_encoder()
        assert enc == "h264_nvenc"


def test_choose_encoder_vaapi_if_only_vaapi_on_linux():
    text = "Encoders:\n V..... libx264 x264\n V..... h264_vaapi H.264 VAAPI encoder\n"
    with patch("subprocess.run") as mock_run, patch("platform.system", return_value="Linux"):
        mock_run.return_value.stdout = text
        mock_run.return_value.stderr = ""
        enc = choose_encoder()
        assert enc == "h264_vaapi"


def test_choose_encoder_for_video_blocks_videotoolbox_over_4k(monkeypatch):
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    monkeypatch.setattr(detect_mod, "ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(detect_mod, "choose_encoder", lambda: "h264_videotoolbox")
    monkeypatch.setattr(detect_mod, "_probe_dimensions", lambda p: (7680, 4320))
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Darwin")
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"))
    assert attempted == "h264_videotoolbox"
    assert enc == "libx264"


def test_choose_encoder_for_video_keeps_hw_on_linux(monkeypatch):
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    monkeypatch.setattr(detect_mod, "ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(detect_mod, "choose_encoder", lambda: "h264_videotoolbox")
    monkeypatch.setattr(detect_mod, "_probe_dimensions", lambda p: (7680, 4320))
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"))
    assert attempted == "h264_videotoolbox"
    assert enc == "h264_videotoolbox"


def test_choose_encoder_for_video_prefers_hevc_when_requested(monkeypatch):
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    monkeypatch.setattr(detect_mod, "ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(detect_mod, "choose_encoder", lambda: "h264_videotoolbox")
    monkeypatch.setattr(detect_mod, "_probe_dimensions", lambda p: (7680, 4320))
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(detect_mod, "_hevc_supported", lambda: True)
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"), prefer_hevc_hw=True)
    assert attempted == "hevc_videotoolbox"
    assert enc == "hevc_videotoolbox"
