"""Tests for lineage index builder and graph traversal."""

from __future__ import annotations

import json
from pathlib import Path

from cosmos.sdk.lineage import Edge, LineageIndex, Node, build_index

# ---------------------------------------------------------------------------
# Helpers — write sidecar JSON fixtures
# ---------------------------------------------------------------------------


def _write_clip(
    dir_path: Path,
    name: str,
    sha: str,
    *,
    ingest_run_id: str = "ing_1",
) -> Path:
    data = {
        "schema_version": "1.0.0",
        "clip_id": f"clip-{name}-{sha[:8]}",
        "ingest_run_id": ingest_run_id,
        "name": name,
        "output": {"path": f"{dir_path / name}.mp4", "sha256": sha, "bytes": 100},
        "video": {"width": 3840, "height": 2160},
    }
    path = dir_path / f"{name}.mp4.cosmos_clip.v1.json"
    path.write_text(json.dumps(data))
    return path


def _write_view(
    dir_path: Path,
    name: str,
    sha: str,
    source_sha: str,
    *,
    crop_run_id: str = "crop_1",
) -> Path:
    data = {
        "schema_version": "1.0.0",
        "view_id": f"view-{name}-{sha[:8]}",
        "crop_run_id": crop_run_id,
        "source": {"path": "source.mp4", "sha256": source_sha},
        "output": {"path": f"{dir_path / name}.mp4", "sha256": sha, "bytes": 50},
        "video": {"width": 1080, "height": 1080},
        "crop": {"size": 1080},
    }
    path = dir_path / f"{name}.mp4.cosmos_view.v1.json"
    path.write_text(json.dumps(data))
    return path


def _write_optimized(
    dir_path: Path,
    name: str,
    sha: str,
    source_sha: str,
    *,
    optimize_run_id: str = "opt_1",
    mode: str = "transcode",
) -> Path:
    data = {
        "schema_version": "1.0.0",
        "optimized_id": f"optimized-{name}-{sha[:8]}",
        "optimize_run_id": optimize_run_id,
        "mode": mode,
        "source": {"path": "source.mp4", "sha256": source_sha},
        "output": {"path": f"{dir_path / name}.mp4", "sha256": sha, "bytes": 40},
        "video": {"width": 1920, "height": 1080},
    }
    path = dir_path / f"{name}.mp4.cosmos_optimized.v1.json"
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


def test_build_empty_dir(tmp_path: Path) -> None:
    index = build_index(tmp_path)
    assert len(index.nodes) == 0
    assert len(index.edges) == 0
    assert index.warnings == []


def test_build_clips_only(tmp_path: Path) -> None:
    _write_clip(tmp_path, "CLIP1", "aaa111")
    _write_clip(tmp_path, "CLIP2", "bbb222")
    index = build_index(tmp_path)
    assert len(index.nodes) == 2
    assert len(index.edges) == 0
    assert "aaa111" in index.nodes
    assert index.nodes["aaa111"].stage == "ingest"
    assert index.nodes["aaa111"].id == "clip-CLIP1-aaa111"


def test_build_clip_to_view_edge(tmp_path: Path) -> None:
    _write_clip(tmp_path, "CLIP1", "aaa111")
    _write_view(tmp_path, "VIEW1", "vvv111", source_sha="aaa111")
    index = build_index(tmp_path)
    assert len(index.nodes) == 2
    assert len(index.edges) == 1
    assert index.edges[0] == Edge(source="aaa111", target="vvv111")


def test_build_full_chain(tmp_path: Path) -> None:
    """clip → view → optimized."""
    _write_clip(tmp_path, "CLIP1", "clip_sha")
    _write_view(tmp_path, "VIEW1", "view_sha", source_sha="clip_sha")
    _write_optimized(tmp_path, "OPT1", "opt_sha", source_sha="view_sha")
    index = build_index(tmp_path)
    assert len(index.nodes) == 3
    assert len(index.edges) == 2


def test_build_multiple_dirs(tmp_path: Path) -> None:
    d1 = tmp_path / "ingest_out"
    d2 = tmp_path / "crop_out"
    d1.mkdir()
    d2.mkdir()
    _write_clip(d1, "CLIP1", "aaa111")
    _write_view(d2, "VIEW1", "vvv111", source_sha="aaa111")
    index = build_index(d1, d2)
    assert len(index.nodes) == 2
    assert len(index.edges) == 1


def test_build_recursive_scan(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested"
    nested.mkdir(parents=True)
    _write_clip(nested, "CLIP1", "aaa111")
    index = build_index(tmp_path)
    assert len(index.nodes) == 1


def test_build_malformed_sidecar_warns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4.cosmos_clip.v1.json"
    bad.write_text("not json")
    index = build_index(tmp_path)
    assert len(index.nodes) == 0
    assert any("malformed" in w for w in index.warnings)


def test_build_missing_sha_warns(tmp_path: Path) -> None:
    path = tmp_path / "x.mp4.cosmos_clip.v1.json"
    path.write_text(json.dumps({"clip_id": "clip-x", "output": {}}))
    index = build_index(tmp_path)
    assert len(index.nodes) == 0
    assert any("missing sha256" in w for w in index.warnings)


def test_build_nondir_warns(tmp_path: Path) -> None:
    f = tmp_path / "not_a_dir.txt"
    f.write_text("hi")
    index = build_index(f)
    assert any("non-directory" in w for w in index.warnings)


# ---------------------------------------------------------------------------
# Graph traversal
# ---------------------------------------------------------------------------


def _make_chain_index() -> LineageIndex:
    """Build a simple 3-node chain: clip → view → optimized."""
    index = LineageIndex()
    index.nodes["clip_sha"] = Node(
        id="clip-A-clip_sha", stage="ingest", sha256="clip_sha", path="A.mp4", sidecar="a.json"
    )
    index.nodes["view_sha"] = Node(
        id="view-B-view_sha", stage="crop", sha256="view_sha", path="B.mp4", sidecar="b.json"
    )
    index.nodes["opt_sha"] = Node(
        id="opt-C-opt_sha", stage="optimize", sha256="opt_sha", path="C.mp4", sidecar="c.json"
    )
    index.edges = [
        Edge(source="clip_sha", target="view_sha"),
        Edge(source="view_sha", target="opt_sha"),
    ]
    return index


def test_upstream_from_leaf() -> None:
    index = _make_chain_index()
    up = index.upstream("opt_sha")
    assert len(up) == 2
    ids = {n.id for n in up}
    assert "clip-A-clip_sha" in ids
    assert "view-B-view_sha" in ids


def test_upstream_from_root() -> None:
    index = _make_chain_index()
    up = index.upstream("clip_sha")
    assert len(up) == 0


def test_downstream_from_root() -> None:
    index = _make_chain_index()
    down = index.downstream("clip_sha")
    assert len(down) == 2
    ids = {n.id for n in down}
    assert "view-B-view_sha" in ids
    assert "opt-C-opt_sha" in ids


def test_downstream_from_leaf() -> None:
    index = _make_chain_index()
    down = index.downstream("opt_sha")
    assert len(down) == 0


def test_chain_includes_self() -> None:
    index = _make_chain_index()
    chain = index.chain("view_sha")
    assert len(chain) == 3
    shas = [n.sha256 for n in chain]
    assert "clip_sha" in shas
    assert "view_sha" in shas
    assert "opt_sha" in shas


def test_tree_nested_structure() -> None:
    index = _make_chain_index()
    tree = index.tree("opt_sha")
    assert tree["id"] == "opt-C-opt_sha"
    assert len(tree["sources"]) == 1
    view_tree = tree["sources"][0]
    assert view_tree["id"] == "view-B-view_sha"
    assert len(view_tree["sources"]) == 1
    clip_tree = view_tree["sources"][0]
    assert clip_tree["id"] == "clip-A-clip_sha"
    assert clip_tree["sources"] == []


def test_tree_unknown_sha_returns_empty() -> None:
    index = _make_chain_index()
    assert index.tree("nonexistent") == {}


# ---------------------------------------------------------------------------
# Fan-out / fan-in
# ---------------------------------------------------------------------------


def test_fan_out_one_clip_multiple_views() -> None:
    index = LineageIndex()
    index.nodes["clip"] = Node(
        id="clip-A", stage="ingest", sha256="clip", path="A.mp4", sidecar="a.json"
    )
    index.nodes["v1"] = Node(
        id="view-1", stage="crop", sha256="v1", path="v1.mp4", sidecar="v1.json"
    )
    index.nodes["v2"] = Node(
        id="view-2", stage="crop", sha256="v2", path="v2.mp4", sidecar="v2.json"
    )
    index.edges = [
        Edge(source="clip", target="v1"),
        Edge(source="clip", target="v2"),
    ]
    down = index.downstream("clip")
    assert len(down) == 2


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def test_to_dict_schema(tmp_path: Path) -> None:
    _write_clip(tmp_path, "CLIP1", "aaa111")
    index = build_index(tmp_path)
    d = index.to_dict()
    assert d["schema"] == "cosmos-lineage-index-v1"
    assert d["node_count"] == 1
    assert d["edge_count"] == 0
    assert isinstance(d["nodes"], list)
    assert isinstance(d["edges"], list)


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    _write_clip(tmp_path, "C1", "sha1")
    _write_view(tmp_path, "V1", "sha2", source_sha="sha1")
    index = build_index(tmp_path)
    out = tmp_path / "lineage.json"
    index.write(out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["node_count"] == 2
    assert data["edge_count"] == 1
