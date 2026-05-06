from __future__ import annotations

from pathlib import Path


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


__all__ = ["_clean_stderr", "_coerce_source_path"]
