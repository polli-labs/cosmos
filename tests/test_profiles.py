"""Unit tests for cosmos.sdk.profiles."""

from __future__ import annotations

import pytest
from cosmos.sdk.profiles import (
    BALANCED,
    STRICT,
    THROUGHPUT,
    list_profiles,
    resolve_profile,
)


class TestResolveProfile:
    def test_none_returns_none(self) -> None:
        assert resolve_profile(None) is None

    def test_strict_by_name(self) -> None:
        p = resolve_profile("strict")
        assert p is STRICT
        assert p is not None
        assert p.name == "strict"
        assert p.pinned_encoder == "libx264"
        assert p.threads == 4
        assert p.bitexact is True

    def test_balanced_by_name(self) -> None:
        p = resolve_profile("balanced")
        assert p is BALANCED
        assert p is not None
        assert p.pinned_encoder is None
        assert p.threads is None
        assert p.bitexact is False

    def test_throughput_by_name(self) -> None:
        p = resolve_profile("throughput")
        assert p is THROUGHPUT
        assert p is not None
        assert p.scale_filter == "bicubic"
        assert p.bitexact is False

    def test_case_insensitive(self) -> None:
        assert resolve_profile("STRICT") is STRICT
        assert resolve_profile("Balanced") is BALANCED

    def test_whitespace_stripped(self) -> None:
        assert resolve_profile("  strict  ") is STRICT

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown determinism profile"):
            resolve_profile("nonexistent")

    def test_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COSMOS_PROFILE", "strict")
        assert resolve_profile(None) is STRICT

    def test_explicit_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COSMOS_PROFILE", "strict")
        assert resolve_profile("throughput") is THROUGHPUT

    def test_env_var_not_set_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COSMOS_PROFILE", raising=False)
        assert resolve_profile(None) is None


class TestListProfiles:
    def test_returns_all_three(self) -> None:
        profiles = list_profiles()
        assert set(profiles.keys()) == {"strict", "balanced", "throughput"}

    def test_returns_copy(self) -> None:
        a = list_profiles()
        b = list_profiles()
        assert a is not b


class TestProfileToDict:
    def test_strict_dict_includes_all_fields(self) -> None:
        d = STRICT.to_dict()
        assert d["name"] == "strict"
        assert d["encoder_policy"] == "pinned-software"
        assert d["pinned_encoder"] == "libx264"
        assert d["threads"] == 4
        assert d["scale_filter"] == "lanczos"
        assert d["bitexact"] is True

    def test_balanced_dict_omits_none_fields(self) -> None:
        d = BALANCED.to_dict()
        assert "pinned_encoder" not in d
        assert "threads" not in d
        assert "scale_filter" not in d

    def test_throughput_dict_has_scale(self) -> None:
        d = THROUGHPUT.to_dict()
        assert d["scale_filter"] == "bicubic"
        assert "threads" not in d


class TestProfileFrozen:
    def test_cannot_mutate(self) -> None:
        with pytest.raises(AttributeError):
            STRICT.name = "mutable"  # type: ignore[misc]
