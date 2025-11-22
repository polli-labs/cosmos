from __future__ import annotations

from pathlib import Path

from cosmos.ffmpeg.detect import ensure_ffmpeg_available


def preflight(input_dir: Path) -> None:
    """Basic preflight checks (extend with upstream logic)."""
    ensure_ffmpeg_available()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
