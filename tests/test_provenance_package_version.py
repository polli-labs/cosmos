from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from cosmos.sdk import provenance


def test_cosmos_package_version_queries_polli_cosmos_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried: list[str] = []

    def _version(distribution_name: str) -> str:
        queried.append(distribution_name)
        return "0.7.1"

    monkeypatch.setattr(provenance, "pkg_version", _version)

    assert provenance.package_version() == "0.7.1"
    assert queried == ["polli-cosmos"]


def test_cosmos_package_version_uses_legacy_cosmos_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried: list[str] = []

    def _version(distribution_name: str) -> str:
        queried.append(distribution_name)
        if distribution_name == "polli-cosmos":
            raise PackageNotFoundError(distribution_name)
        return "0.6.0"

    monkeypatch.setattr(provenance, "pkg_version", _version)

    assert provenance.package_version() == "0.6.0"
    assert queried == ["polli-cosmos", "cosmos"]


def test_cosmos_package_version_returns_zero_after_known_names_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried: list[str] = []

    def _version(distribution_name: str) -> str:
        queried.append(distribution_name)
        raise PackageNotFoundError(distribution_name)

    monkeypatch.setattr(provenance, "pkg_version", _version)

    assert provenance.package_version() == "0.0.0"
    assert queried == ["polli-cosmos", "cosmos"]


def test_emit_crop_run_records_resolved_package_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(provenance, "pkg_version", lambda _distribution_name: "0.7.1")
    monkeypatch.setattr(provenance, "ffmpeg_version", lambda: {"version": "test", "path": "ffmpeg"})
    monkeypatch.setattr(provenance, "system_info", lambda: {"python": "test"})

    _run_id, run_path = provenance.emit_crop_run(output_dir=tmp_path, jobs=[])

    payload = json.loads(run_path.read_text())
    assert payload["version"] == "0.7.1"
    assert payload["version"] != "0.0.0"
