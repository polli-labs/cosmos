from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from cosmos.sdk.optimize import OptimizeOptions, optimize

optimize_mod = importlib.import_module("cosmos.sdk.optimize")


@pytest.fixture(autouse=True)
def _mock_ffmpeg_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(optimize_mod, "ensure_ffmpeg_available", lambda: None)


def test_optimize_dry_run_emits_plan_and_run_artifact(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"

    outputs = optimize(
        [src],
        out_dir,
        options=OptimizeOptions(dry_run=True),
    )

    expected_out = out_dir / "clip_optimized.mp4"
    assert outputs == [expected_out]
    assert (out_dir / "cosmos_optimize_run.v1.json").exists()
    plan_path = out_dir / "cosmos_optimize_dry_run.json"
    assert plan_path.exists()
    payload = json.loads(plan_path.read_text())
    assert payload["planned"][0]["mode"] == "remux"
    assert payload["planned"][0]["output"] == str(expected_out)


def test_optimize_auto_selects_transcode_with_transform_flags(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"

    optimize(
        [src],
        out_dir,
        options=OptimizeOptions(
            dry_run=True,
            target_height=1080,
            fps=30.0,
        ),
    )

    plan_path = out_dir / "cosmos_optimize_dry_run.json"
    payload = json.loads(plan_path.read_text())
    assert payload["planned"][0]["mode"] == "transcode"
    cmd = " ".join(payload["planned"][0]["command"])
    assert "scale=-2:1080:flags=lanczos" in cmd
    assert "fps=30" in cmd


def test_optimize_requires_force_for_existing_outputs(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "clip_optimized.mp4"
    existing.write_bytes(b"already-there")

    with pytest.raises(FileExistsError):
        optimize(
            [src],
            out_dir,
            options=OptimizeOptions(dry_run=True),
        )
