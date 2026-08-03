from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import (
        PreviewRunResult,
        RenderOptions,
        generate_preview_for_curated_pairs,
        generate_preview_for_jobs,
    )

__all__ = [
    "PreviewRunResult",
    "RenderOptions",
    "generate_preview_for_jobs",
    "generate_preview_for_curated_pairs",
]


if not TYPE_CHECKING:

    def __getattr__(name: str) -> object:
        if name not in __all__:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        value = getattr(import_module("cosmos.preview.pipeline"), name)
        globals()[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted(set(globals()) | set(__all__))
