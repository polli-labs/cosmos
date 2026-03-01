"""CLI contract tests for ``cosmos lineage`` subcommands."""

from __future__ import annotations

import json
from pathlib import Path

from cosmos.cli.cosmos_app import app
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers — minimal sidecar fixtures
# ---------------------------------------------------------------------------


def _write_clip(d: Path, name: str, sha: str) -> None:
    (d / f"{name}.mp4.cosmos_clip.v1.json").write_text(
        json.dumps(
            {
                "clip_id": f"clip-{name}-{sha[:8]}",
                "ingest_run_id": "ing_1",
                "output": {"path": str(d / f"{name}.mp4"), "sha256": sha, "bytes": 100},
                "video": {"width": 3840, "height": 2160},
            }
        )
    )


def _write_view(d: Path, name: str, sha: str, source_sha: str) -> None:
    (d / f"{name}.mp4.cosmos_view.v1.json").write_text(
        json.dumps(
            {
                "view_id": f"view-{name}-{sha[:8]}",
                "crop_run_id": "crop_1",
                "source": {"path": "clip.mp4", "sha256": source_sha},
                "output": {"path": str(d / f"{name}.mp4"), "sha256": sha, "bytes": 50},
                "video": {"width": 1080, "height": 1080},
            }
        )
    )


def _write_optimized(d: Path, name: str, sha: str, source_sha: str) -> None:
    (d / f"{name}.mp4.cosmos_optimized.v1.json").write_text(
        json.dumps(
            {
                "optimized_id": f"optimized-{name}-{sha[:8]}",
                "optimize_run_id": "opt_1",
                "mode": "transcode",
                "source": {"path": "view.mp4", "sha256": source_sha},
                "output": {"path": str(d / f"{name}.mp4"), "sha256": sha, "bytes": 40},
                "video": {"width": 1920, "height": 1080},
            }
        )
    )


def _make_chain(d: Path) -> None:
    _write_clip(d, "CLIP1", "aaa111")
    _write_view(d, "VIEW1", "bbb222", source_sha="aaa111")
    _write_optimized(d, "OPT1", "ccc333", source_sha="bbb222")


# ---------------------------------------------------------------------------
# cosmos lineage build
# ---------------------------------------------------------------------------


def test_lineage_build_json(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "build", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == "cosmos-lineage-index-v1"
    assert payload["node_count"] == 3
    assert payload["edge_count"] == 2
    assert payload["command"] == "cosmos lineage build"


def test_lineage_build_output_file(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    out = tmp_path / "index.json"
    result = runner.invoke(app, ["lineage", "build", str(tmp_path), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["node_count"] == 3


def test_lineage_build_plain(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "build", str(tmp_path), "--plain"])
    assert result.exit_code == 0
    assert "3\t2" in result.stdout


def test_lineage_build_empty_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["lineage", "build", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["node_count"] == 0


# ---------------------------------------------------------------------------
# cosmos lineage upstream
# ---------------------------------------------------------------------------


def test_lineage_upstream_json(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "upstream", "ccc333", "--in", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos lineage upstream"
    assert payload["count"] == 2
    assert payload["root"]["sha256"] == "ccc333"
    ids = {r["id"] for r in payload["results"]}
    assert "clip-CLIP1-aaa111" in ids
    assert "view-VIEW1-bbb222" in ids


def test_lineage_upstream_by_id(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(
        app,
        ["lineage", "upstream", "optimized-OPT1-ccc333", "--in", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 2


def test_lineage_upstream_prefix_match(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "upstream", "ccc", "--in", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 2


def test_lineage_upstream_root_returns_empty(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "upstream", "aaa111", "--in", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 0


def test_lineage_upstream_not_found(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "upstream", "nonexistent", "--in", str(tmp_path)])
    assert result.exit_code == 3


# ---------------------------------------------------------------------------
# cosmos lineage downstream
# ---------------------------------------------------------------------------


def test_lineage_downstream_json(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(
        app, ["lineage", "downstream", "aaa111", "--in", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos lineage downstream"
    assert payload["count"] == 2
    ids = {r["id"] for r in payload["results"]}
    assert "view-VIEW1-bbb222" in ids
    assert "optimized-OPT1-ccc333" in ids


def test_lineage_downstream_leaf_returns_empty(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(
        app, ["lineage", "downstream", "ccc333", "--in", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 0


# ---------------------------------------------------------------------------
# cosmos lineage chain
# ---------------------------------------------------------------------------


def test_lineage_chain_json(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "chain", "bbb222", "--in", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos lineage chain"
    assert payload["count"] == 3
    stages = [r["stage"] for r in payload["results"]]
    assert "ingest" in stages
    assert "crop" in stages
    assert "optimize" in stages


def test_lineage_chain_plain(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "chain", "bbb222", "--in", str(tmp_path), "--plain"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# cosmos lineage tree
# ---------------------------------------------------------------------------


def test_lineage_tree_json(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "tree", "ccc333", "--in", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos lineage tree"
    tree = payload["tree"]
    assert tree["stage"] == "optimize"
    assert len(tree["sources"]) == 1
    assert tree["sources"][0]["stage"] == "crop"
    assert tree["sources"][0]["sources"][0]["stage"] == "ingest"


def test_lineage_tree_not_found(tmp_path: Path) -> None:
    _make_chain(tmp_path)
    result = runner.invoke(app, ["lineage", "tree", "missing", "--in", str(tmp_path)])
    assert result.exit_code == 3


# ---------------------------------------------------------------------------
# cosmos lineage appears in help
# ---------------------------------------------------------------------------


def test_lineage_visible_in_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "lineage" in result.stdout


def test_lineage_subcommands_in_help() -> None:
    result = runner.invoke(app, ["lineage", "--help"])
    assert result.exit_code == 0
    for sub in ("build", "upstream", "downstream", "chain", "tree"):
        assert sub in result.stdout
