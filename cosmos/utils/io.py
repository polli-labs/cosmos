from __future__ import annotations

from pathlib import Path


def find_videos(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.mp4"))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
