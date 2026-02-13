"""Auto-bootstrap an NVENC-capable ffmpeg on Linux when the system build lacks it."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

BTBN_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-linux64-gpl.tar.xz"
)

COSMOS_BIN_DIR = Path.home() / ".local" / "share" / "cosmos" / "bin"


def download_btbn_ffmpeg(dest: Path | None = None) -> Path:
    """Download the BtbN static ffmpeg build and extract ffmpeg + ffprobe.

    Returns the directory containing the extracted binaries.
    """
    dest = dest or COSMOS_BIN_DIR
    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "ffmpeg.tar.xz"
        logger.info("Downloading NVENC-capable ffmpeg from BtbN (~135 MB)...")
        urlretrieve(BTBN_URL, archive)  # noqa: S310

        logger.info("Extracting ffmpeg and ffprobe...")
        with tarfile.open(archive, "r:xz") as tar:
            for member in tar.getmembers():
                basename = Path(member.name).name
                if basename in ("ffmpeg", "ffprobe") and member.isfile():
                    with tar.extractfile(member) as src:  # type: ignore[union-attr]
                        if src is None:
                            continue
                        out_path = dest / basename
                        with open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        out_path.chmod(0o755)
                        logger.info("Installed %s -> %s", basename, out_path)

    # Verify the binaries exist
    ffmpeg_path = dest / "ffmpeg"
    ffprobe_path = dest / "ffprobe"
    if not ffmpeg_path.exists() or not ffprobe_path.exists():
        msg = f"Failed to extract ffmpeg/ffprobe to {dest}"
        raise RuntimeError(msg)

    # Quick sanity check
    try:
        out = subprocess.run(  # noqa: S603
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            first_line = (out.stdout or "").split("\n")[0]
            logger.info("Verified: %s", first_line)
    except Exception:
        logger.warning("Could not verify installed ffmpeg binary")

    return dest


def cosmos_managed_ffmpeg() -> Path | None:
    """Return path to cosmos-managed ffmpeg if it exists and is executable."""
    ffmpeg = COSMOS_BIN_DIR / "ffmpeg"
    if ffmpeg.is_file() and os.access(ffmpeg, os.X_OK):
        return ffmpeg
    return None


def cosmos_managed_ffprobe() -> Path | None:
    """Return path to cosmos-managed ffprobe if it exists and is executable."""
    ffprobe = COSMOS_BIN_DIR / "ffprobe"
    if ffprobe.is_file() and os.access(ffprobe, os.X_OK):
        return ffprobe
    return None
