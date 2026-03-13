"""Ingest adapter registry and auto-detection.

``resolve_adapter`` is the single entry-point used by the SDK orchestrator
to obtain the correct ``IngestAdapter`` for a given input directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from cosmos.ingest.adapter import IngestAdapter


# Registry: checked in order; first ``detect()`` wins.
def _builtin_adapters() -> list[Any]:
    """Return built-in adapter classes in detection-priority order."""
    from cosmos.ingest.adapters.cosm import CosmAdapter
    from cosmos.ingest.adapters.generic_media import GenericMediaAdapter

    return [CosmAdapter, GenericMediaAdapter]


def resolve_adapter(
    input_dir: Path,
    *,
    adapter_name: str | None = None,
) -> IngestAdapter:
    """Return an adapter instance suitable for *input_dir*.

    Parameters
    ----------
    input_dir:
        Root of the source media tree.
    adapter_name:
        Explicit adapter selector (e.g. ``"cosm"``, ``"generic-media"``).
        When ``None``, adapters are probed via ``detect()`` in priority
        order; the first match wins.

    Raises
    ------
    ValueError
        If *adapter_name* is given but unknown, or if no adapter matches
        during auto-detection.
    """
    adapters = _builtin_adapters()

    if adapter_name is not None:
        for cls in adapters:
            inst: IngestAdapter = cls()
            if inst.name == adapter_name:
                return inst
        known = ", ".join(cls().name for cls in adapters)
        raise ValueError(f"Unknown adapter {adapter_name!r}. Available: {known}")

    # Auto-detect
    for cls in adapters:
        if cls.detect(input_dir):
            return cast(IngestAdapter, cls())

    raise ValueError(
        f"No adapter could handle {input_dir}. "
        "Pass --adapter explicitly or check your input directory."
    )


__all__ = ["resolve_adapter"]
