"""Determinism profiles for reproducibility-vs-throughput trade-offs.

Profiles provide named presets that control encoder selection, thread pinning,
scale filter, and bitexact flags across ingest/crop/optimize.  When no profile
is set, behaviour is identical to pre-profile Cosmos releases.

Resolution precedence:  explicit CLI ``--profile`` > ``COSMOS_PROFILE`` env > ``None``.
Per-field CLI overrides always win over profile defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

ProfileName = Literal["strict", "balanced", "throughput"]


@dataclass(frozen=True)
class DeterminismProfile:
    """Immutable description of a determinism profile."""

    name: ProfileName
    encoder_policy: Literal["pinned-software", "auto-fallback", "prefer-hardware"]
    pinned_encoder: str | None
    threads: int | None
    scale_filter: str | None
    bitexact: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a provenance-friendly dict (no ``None`` values)."""
        d: dict[str, Any] = {
            "name": self.name,
            "encoder_policy": self.encoder_policy,
            "bitexact": self.bitexact,
        }
        if self.pinned_encoder is not None:
            d["pinned_encoder"] = self.pinned_encoder
        if self.threads is not None:
            d["threads"] = self.threads
        if self.scale_filter is not None:
            d["scale_filter"] = self.scale_filter
        return d


STRICT = DeterminismProfile(
    name="strict",
    encoder_policy="pinned-software",
    pinned_encoder="libx264",
    threads=4,
    scale_filter="lanczos",
    bitexact=True,
    description=(
        "Maximum reproducibility: software encoder, pinned threads, bitexact output. "
        "Designed for CI and cross-host comparison."
    ),
)

BALANCED = DeterminismProfile(
    name="balanced",
    encoder_policy="auto-fallback",
    pinned_encoder=None,
    threads=None,
    scale_filter=None,
    bitexact=False,
    description=(
        "Default behaviour: auto hardware detection with software fallback. "
        "Equivalent to pre-profile Cosmos runs."
    ),
)

THROUGHPUT = DeterminismProfile(
    name="throughput",
    encoder_policy="prefer-hardware",
    pinned_encoder=None,
    threads=None,
    scale_filter="bicubic",
    bitexact=False,
    description=(
        "Maximum throughput: prefer hardware encoders, faster presets, "
        "bicubic scaling. For bulk processing."
    ),
)

_PROFILES: dict[str, DeterminismProfile] = {
    "strict": STRICT,
    "balanced": BALANCED,
    "throughput": THROUGHPUT,
}


def resolve_profile(name: str | None = None) -> DeterminismProfile | None:
    """Resolve a determinism profile by name.

    Precedence: explicit *name* > ``COSMOS_PROFILE`` env var > ``None``.
    Returns ``None`` when no profile is active (preserving legacy behaviour).
    """
    effective = name or os.environ.get("COSMOS_PROFILE")
    if effective is None:
        return None
    effective = effective.strip().lower()
    if effective not in _PROFILES:
        valid = ", ".join(sorted(_PROFILES))
        raise ValueError(f"Unknown determinism profile {effective!r}. Valid profiles: {valid}")
    return _PROFILES[effective]


def list_profiles() -> dict[str, DeterminismProfile]:
    """Return all registered profiles (name -> profile)."""
    return dict(_PROFILES)
