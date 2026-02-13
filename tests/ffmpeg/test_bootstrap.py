"""Tests for ffmpeg bootstrap and binary resolution logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def test_resolve_ffmpeg_path_env_override(monkeypatch):
    """COSMOS_FFMPEG env var takes highest priority."""
    monkeypatch.setenv("COSMOS_FFMPEG", "/custom/ffmpeg")
    from cosmos.ffmpeg.detect import resolve_ffmpeg_path

    assert resolve_ffmpeg_path() == "/custom/ffmpeg"


def test_resolve_ffmpeg_path_cosmos_managed(monkeypatch, tmp_path):
    """Cosmos-managed binary takes priority over system PATH."""
    monkeypatch.delenv("COSMOS_FFMPEG", raising=False)
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.touch()
    fake_ffmpeg.chmod(0o755)

    import cosmos.ffmpeg.bootstrap as bootstrap_mod

    monkeypatch.setattr(bootstrap_mod, "COSMOS_BIN_DIR", tmp_path)
    from cosmos.ffmpeg.detect import resolve_ffmpeg_path

    result = resolve_ffmpeg_path()
    assert result == str(fake_ffmpeg)


def test_resolve_ffmpeg_path_system_fallback(monkeypatch):
    """Falls back to system PATH when no env var or managed binary."""
    monkeypatch.delenv("COSMOS_FFMPEG", raising=False)

    import cosmos.ffmpeg.bootstrap as bootstrap_mod

    monkeypatch.setattr(bootstrap_mod, "COSMOS_BIN_DIR", Path("/nonexistent"))
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)
    from cosmos.ffmpeg.detect import resolve_ffmpeg_path

    assert resolve_ffmpeg_path() == "/usr/bin/ffmpeg"


def test_resolve_ffprobe_path_env_override(monkeypatch):
    """COSMOS_FFPROBE env var takes highest priority."""
    monkeypatch.setenv("COSMOS_FFPROBE", "/custom/ffprobe")
    from cosmos.ffmpeg.detect import resolve_ffprobe_path

    assert resolve_ffprobe_path() == "/custom/ffprobe"


def test_check_nvidia_available_linux_with_nvidia_smi(monkeypatch):
    """Detects NVIDIA GPU when nvidia-smi is on PATH."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        detect_mod.shutil, "which", lambda x: "/usr/bin/nvidia-smi" if x == "nvidia-smi" else None
    )
    assert detect_mod.check_nvidia_available() is True


def test_check_nvidia_available_linux_proc_driver(monkeypatch):
    """Detects NVIDIA GPU via /proc/driver/nvidia/version."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod.shutil, "which", lambda x: None)
    monkeypatch.setattr(
        detect_mod.Path,
        "exists",
        lambda p: p.as_posix() == "/proc/driver/nvidia/version",
    )
    assert detect_mod.check_nvidia_available() is True


def test_check_nvidia_available_macos(monkeypatch):
    """Always False on macOS."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Darwin")
    assert detect_mod.check_nvidia_available() is False


def test_prompt_bootstrap_skips_on_macos(monkeypatch):
    """Does nothing on macOS."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Darwin")
    # Should not raise or prompt
    detect_mod.prompt_bootstrap_if_needed(interactive=False)


def test_prompt_bootstrap_skips_when_nvenc_present(monkeypatch):
    """Does nothing when ffmpeg already has h264_nvenc."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod, "check_nvidia_available", lambda: True)
    monkeypatch.setattr(detect_mod, "resolve_ffmpeg_path", lambda: "/usr/bin/ffmpeg")

    mock_run = MagicMock()
    mock_run.return_value.stdout = "h264_nvenc"
    mock_run.return_value.stderr = ""
    monkeypatch.setattr(detect_mod.subprocess, "run", mock_run)

    # Should not raise or try to download
    detect_mod.prompt_bootstrap_if_needed(interactive=False)


def test_prompt_bootstrap_warns_non_interactive(monkeypatch, caplog):
    """Logs a warning in non-interactive mode when NVENC is missing."""
    import cosmos.ffmpeg.detect as detect_mod

    monkeypatch.setattr(detect_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detect_mod, "check_nvidia_available", lambda: True)
    monkeypatch.setattr(detect_mod, "resolve_ffmpeg_path", lambda: "/usr/bin/ffmpeg")

    mock_run = MagicMock()
    mock_run.return_value.stdout = "libx264"
    mock_run.return_value.stderr = ""
    monkeypatch.setattr(detect_mod.subprocess, "run", mock_run)

    import logging

    with caplog.at_level(logging.WARNING):
        detect_mod.prompt_bootstrap_if_needed(interactive=False)

    assert "NVIDIA GPU detected" in caplog.text
    assert "h264_nvenc" in caplog.text


def test_cosmos_managed_ffmpeg_returns_none_when_missing(monkeypatch):
    """Returns None when the managed directory doesn't exist."""
    import cosmos.ffmpeg.bootstrap as bootstrap_mod

    monkeypatch.setattr(bootstrap_mod, "COSMOS_BIN_DIR", Path("/nonexistent"))
    assert bootstrap_mod.cosmos_managed_ffmpeg() is None


def test_cosmos_managed_ffmpeg_returns_path(monkeypatch, tmp_path):
    """Returns the path when the managed ffmpeg exists and is executable."""
    import cosmos.ffmpeg.bootstrap as bootstrap_mod

    monkeypatch.setattr(bootstrap_mod, "COSMOS_BIN_DIR", tmp_path)
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.touch()
    ffmpeg.chmod(0o755)
    result = bootstrap_mod.cosmos_managed_ffmpeg()
    assert result == ffmpeg
