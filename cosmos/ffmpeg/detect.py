from __future__ import annotations

import platform
import shutil
import subprocess


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH")


def choose_encoder() -> str:
    """Prefer the best available hardware H.264 encoder by platform.

    macOS: h264_videotoolbox > libx264
    Linux: h264_nvenc > h264_qsv > h264_vaapi > libx264
    Windows: h264_nvenc > h264_qsv > h264_amf > libx264
    """
    ensure_ffmpeg_available()
    try:
        ff = shutil.which("ffmpeg") or "ffmpeg"
        out = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True)  # noqa: S603
        stdout = out.stdout if isinstance(getattr(out, "stdout", None), str) else ""
        stderr = out.stderr if isinstance(getattr(out, "stderr", None), str) else ""
        text = (stdout + stderr).lower()
    except Exception:
        return "libx264"

    sys = platform.system().lower()
    if sys == "darwin":
        order = ["h264_videotoolbox", "libx264"]
    elif sys == "windows":
        order = ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]
    else:
        # linux and others
        order = ["h264_nvenc", "h264_qsv", "h264_vaapi", "libx264"]

    for enc in order:
        if enc == "libx264" or enc in text:
            return enc
    return "libx264"
