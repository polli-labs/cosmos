from __future__ import annotations

import math
import os
from pathlib import Path

_VIDEO_SUBPROCESS_TIMEOUT_ENV = "COSMOS_VIDEO_FFMPEG_TIMEOUT"


def _coerce_source_path(path: Path | str, *, error_cls: type[Exception]) -> Path:
    source_path = Path(path).expanduser()
    if not source_path.exists():
        raise error_cls(f"Video source does not exist: {source_path}")
    if not source_path.is_file():
        raise error_cls(f"Video source is not a file: {source_path}")
    return source_path


def _clean_stderr(stderr: object) -> str:
    if isinstance(stderr, bytes):
        text = stderr.decode("utf-8", errors="replace")
    elif isinstance(stderr, str):
        text = stderr
    else:
        text = ""
    return text.strip() or "no stderr"


def _video_subprocess_timeout_seconds() -> float | None:
    raw = os.environ.get(_VIDEO_SUBPROCESS_TIMEOUT_ENV)
    if raw is None or raw.strip() == "":
        return None
    try:
        timeout = float(raw)
    except ValueError:
        return None
    if not math.isfinite(timeout) or timeout <= 0:
        return None
    return timeout


def _format_timeout(timeout: float | None) -> str:
    return "unbounded" if timeout is None else f"{timeout:g}s"


__all__ = [
    "_clean_stderr",
    "_coerce_source_path",
    "_format_timeout",
    "_video_subprocess_timeout_seconds",
]
