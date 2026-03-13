import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available on PATH", allow_module_level=True)

from cosmos.ffmpeg.detect import choose_encoder, choose_encoder_for_video, ensure_ffmpeg_available


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
    monkeypatch.setattr(detect_mod, "_encoder_runtime_usable", lambda _p, _e: True)
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"))
    assert attempted == "h264_videotoolbox"
    assert enc == "libx264"


def test_choose_encoder_for_video_keeps_hw_on_linux(monkeypatch):
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    monkeypatch.setattr(detect_mod, "ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(detect_mod, "choose_encoder", lambda: "h264_videotoolbox")
    monkeypatch.setattr(detect_mod, "_probe_dimensions", lambda p: (7680, 4320))
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod, "_encoder_runtime_usable", lambda _p, _e: True)
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
    monkeypatch.setattr(detect_mod, "_encoder_runtime_usable", lambda _p, _e: True)
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"), prefer_hevc_hw=True)
    assert attempted == "hevc_videotoolbox"
    assert enc == "hevc_videotoolbox"


def test_choose_encoder_for_video_falls_back_when_runtime_probe_fails(monkeypatch):
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    monkeypatch.setattr(detect_mod, "ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(detect_mod, "choose_encoder", lambda: "h264_nvenc")
    monkeypatch.setattr(detect_mod, "_probe_dimensions", lambda p: (1920, 1080))
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod, "_encoder_runtime_usable", lambda _p, _e: False)
    enc, attempted = choose_encoder_for_video(Path("dummy.mp4"))
    assert attempted == "h264_nvenc"
    assert enc == "libx264"


def test_ensure_ffmpeg_available_rejects_missing_explicit_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_FFMPEG", "/definitely/missing/ffmpeg")
    with pytest.raises(RuntimeError, match="binary not found"):
        ensure_ffmpeg_available()


def test_ensure_ffmpeg_available_rejects_non_executable_binary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho no\n")
    fake.chmod(0o755)
    monkeypatch.setenv("COSMOS_FFMPEG", str(fake))
    monkeypatch.setattr(detect_mod.os, "access", lambda _path, _mode: False)
    with pytest.raises(RuntimeError, match="not executable"):
        ensure_ffmpeg_available()


def test_encoder_runtime_probe_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    import cosmos.ffmpeg.detect as detect_mod  # late import for monkeypatching

    detect_mod._ENCODER_RUNTIME_CACHE.clear()
    calls = {"count": 0}

    def _fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        _ = (args, kwargs)
        calls["count"] += 1
        raise subprocess.CalledProcessError(255, ["ffmpeg"])

    monkeypatch.setattr(detect_mod, "resolve_ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod.subprocess, "run", _fake_run)

    assert detect_mod._encoder_runtime_usable(Path("dummy.mp4"), "h264_nvenc") is False
    assert detect_mod._encoder_runtime_usable(Path("dummy2.mp4"), "h264_nvenc") is False
    assert calls["count"] == 1
