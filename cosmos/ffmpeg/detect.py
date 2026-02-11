from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from pathlib import Path

FFPROBE_DIM_CMD = [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=width,height",
    "-of",
    "csv=p=0:s=x",
]


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


def _probe_dimensions(input_path: Path) -> tuple[int | None, int | None]:
    """Return (width, height) using ffprobe; tolerate failures."""
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    try:
        out = subprocess.run(  # noqa: S603
            [ffprobe, *FFPROBE_DIM_CMD, str(input_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        parts = (out.stdout or "").strip().split("x")
        if len(parts) == 2:
            w, h = int(parts[0]), int(parts[1])
            return w, h
    except Exception:
        return None, None
    return None, None


def _is_over_videotoolbox_h264_limit(width: int | None, height: int | None) -> bool:
    """Heuristic guardrail for macOS H.264 VideoToolbox.

    Empirically VT H.264 rejects >4K inputs on M1 (8K sources fail with exit 187).
    Use a conservative 4096px per-dimension threshold.
    """
    if width is None or height is None:
        return False
    return width > 4096 or height > 4096


def _hevc_supported() -> bool:
    ff = shutil.which("ffmpeg") or "ffmpeg"
    try:
        out = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True)  # noqa: S603
        text = (out.stdout or "") + (out.stderr or "")
        return "hevc_videotoolbox" in text
    except Exception:
        return False


def choose_encoder_for_video(input_path: Path, *, prefer_hevc_hw: bool = False) -> tuple[str, str]:
    """Pick encoder and return (encoder_used, encoder_attempted).

    Applies platform/size heuristics to avoid known VideoToolbox H.264 limits.
    """
    ensure_ffmpeg_available()
    candidate = choose_encoder()
    attempted = candidate

    sys = platform.system().lower()
    if sys == "darwin":
        w, h = _probe_dimensions(input_path)
        if prefer_hevc_hw and _hevc_supported():
            return "hevc_videotoolbox", "hevc_videotoolbox"
        if candidate == "h264_videotoolbox" and _is_over_videotoolbox_h264_limit(w, h):
            logging.getLogger(__name__).warning(
                "VideoToolbox H.264 not used: input %s is %sx%s (>4K). "
                "Falling back to libx264. Tip: pass --prefer-hevc-hw to try hevc_videotoolbox.",
                input_path,
                w,
                h,
            )
            return "libx264", attempted
    return candidate, attempted
