from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe binary resolution
# ---------------------------------------------------------------------------


def resolve_ffmpeg_path() -> str:
    """Resolve the ffmpeg binary using the cosmos lookup order.

    1. ``COSMOS_FFMPEG`` env var (explicit override)
    2. ``~/.local/share/cosmos/bin/ffmpeg`` (cosmos-managed install)
    3. System PATH (``shutil.which("ffmpeg")``)
    """
    env = os.environ.get("COSMOS_FFMPEG")
    if env:
        return env

    from cosmos.ffmpeg.bootstrap import cosmos_managed_ffmpeg

    managed = cosmos_managed_ffmpeg()
    if managed is not None:
        return str(managed)

    return shutil.which("ffmpeg") or "ffmpeg"


def resolve_ffprobe_path() -> str:
    """Resolve the ffprobe binary using the same lookup order as ffmpeg."""
    env = os.environ.get("COSMOS_FFPROBE")
    if env:
        return env

    from cosmos.ffmpeg.bootstrap import cosmos_managed_ffprobe

    managed = cosmos_managed_ffprobe()
    if managed is not None:
        return str(managed)

    return shutil.which("ffprobe") or "ffprobe"


def ensure_ffmpeg_available() -> None:
    """Raise if no ffmpeg can be found via the standard lookup order."""
    ff = resolve_ffmpeg_path()
    if ff == "ffmpeg" and shutil.which("ffmpeg") is None:
        hint = ""
        if platform.system().lower() == "darwin":
            hint = " Tip: brew install ffmpeg"
        raise RuntimeError(f"ffmpeg not found in PATH.{hint}")


# ---------------------------------------------------------------------------
# NVIDIA detection + bootstrap prompt
# ---------------------------------------------------------------------------


def check_nvidia_available() -> bool:
    """Return True if NVIDIA GPU drivers are present on a Linux system."""
    if platform.system().lower() != "linux":
        return False
    if shutil.which("nvidia-smi") is not None:
        return True
    return Path("/proc/driver/nvidia/version").exists()


def prompt_bootstrap_if_needed(*, interactive: bool = True) -> None:
    """Detect missing NVENC support on Linux+NVIDIA and offer to bootstrap.

    Does nothing on macOS/Windows, when no NVIDIA GPU is detected, or when
    the resolved ffmpeg already supports h264_nvenc.
    """
    if platform.system().lower() != "linux":
        return
    if not check_nvidia_available():
        return

    ff = resolve_ffmpeg_path()
    try:
        out = subprocess.run(  # noqa: S603
            [ff, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
        )
        text = ((out.stdout or "") + (out.stderr or "")).lower()
    except Exception:
        return

    if "h264_nvenc" in text:
        return

    # NVIDIA present but ffmpeg lacks NVENC
    logger.warning(
        "NVIDIA GPU detected but your ffmpeg (%s) does not support "
        "hardware encoding (h264_nvenc). Software encoding will be "
        "significantly slower.",
        ff,
    )

    if not interactive:
        logger.info(
            "Run without --skip-ffmpeg-check to interactively install "
            "an NVENC-capable ffmpeg build."
        )
        return

    try:
        import questionary

        proceed = questionary.confirm(
            "Download and install an NVENC-enabled ffmpeg build? "
            "This is a ~135 MB download from github.com/BtbN/FFmpeg-Builds.",
            default=True,
        ).ask()
    except (ImportError, EOFError, KeyboardInterrupt):
        proceed = False

    if not proceed:
        logger.info("Skipping ffmpeg bootstrap. Continuing with software encoding.")
        return

    from cosmos.ffmpeg.bootstrap import download_btbn_ffmpeg

    download_btbn_ffmpeg()
    logger.info("Bootstrap complete. NVENC-capable ffmpeg is now available.")


# ---------------------------------------------------------------------------
# Encoder selection
# ---------------------------------------------------------------------------


def choose_encoder() -> str:
    """Prefer the best available hardware H.264 encoder by platform.

    macOS: h264_videotoolbox > libx264
    Linux: h264_nvenc > h264_qsv > h264_vaapi > libx264
    Windows: h264_nvenc > h264_qsv > h264_amf > libx264
    """
    ensure_ffmpeg_available()
    try:
        ff = resolve_ffmpeg_path()
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
    ffprobe = resolve_ffprobe_path()
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
    ff = resolve_ffmpeg_path()
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
