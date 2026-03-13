"""Lineage index builder and graph traversal for Cosmos provenance artifacts.

Builds a directed acyclic graph (DAG) from sidecar provenance artifacts
emitted by ingest, crop, and optimize pipelines. Supports upstream/downstream
queries and full chain traversal.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

STAGES = ("ingest", "crop", "optimize")

_STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}


@dataclass(frozen=True)
class Node:
    """A single provenance artifact in the lineage graph."""

    id: str
    stage: str
    sha256: str
    path: str
    sidecar: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "stage": self.stage,
            "sha256": self.sha256,
            "path": self.path,
            "sidecar": self.sidecar,
        }


@dataclass(frozen=True)
class Edge:
    """A directed dependency edge: *source* was used to produce *target*."""

    source: str  # sha256 of upstream artifact
    target: str  # sha256 of downstream artifact

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target}


@dataclass
class LineageIndex:
    """In-memory lineage graph built from sidecar provenance files."""

    nodes: dict[str, Node] = field(default_factory=dict)  # keyed by sha256
    edges: list[Edge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Serialisation
    # -------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        sorted_nodes = sorted(self.nodes.values(), key=_node_sort_key)
        sorted_edges = sorted(self.edges, key=lambda e: (e.source, e.target))
        return {
            "schema": "cosmos-lineage-index-v1",
            "node_count": len(sorted_nodes),
            "edge_count": len(sorted_edges),
            "nodes": [n.to_dict() for n in sorted_nodes],
            "edges": [e.to_dict() for e in sorted_edges],
            "warnings": self.warnings,
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    # -------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------

    def upstream(self, sha256: str) -> list[Node]:
        """Return all transitive ancestors of the node identified by *sha256*."""
        return self._traverse(sha256, direction="up")

    def downstream(self, sha256: str) -> list[Node]:
        """Return all transitive descendants of the node identified by *sha256*."""
        return self._traverse(sha256, direction="down")

    def tree(self, sha256: str) -> dict[str, Any]:
        """Return a nested tree dict rooted at the node (upstream direction)."""
        node = self.nodes.get(sha256)
        if node is None:
            return {}
        parents = self._direct_parents(sha256)
        return {
            **node.to_dict(),
            "sources": [self.tree(p.sha256) for p in parents],
        }

    def chain(self, sha256: str) -> list[Node]:
        """Return the full lineage chain (upstream + self + downstream), de-duped."""
        up = self.upstream(sha256)
        down = self.downstream(sha256)
        node = self.nodes.get(sha256)
        seen: set[str] = set()
        result: list[Node] = []
        for n in up + ([node] if node else []) + down:
            if n.sha256 not in seen:
                seen.add(n.sha256)
                result.append(n)
        return sorted(result, key=_node_sort_key)

    # -------------------------------------------------------------------
    # Internal traversal
    # -------------------------------------------------------------------

    def _direct_parents(self, sha256: str) -> list[Node]:
        parents: list[Node] = []
        for edge in self.edges:
            if edge.target == sha256:
                node = self.nodes.get(edge.source)
                if node is not None:
                    parents.append(node)
        return parents

    def _direct_children(self, sha256: str) -> list[Node]:
        children: list[Node] = []
        for edge in self.edges:
            if edge.source == sha256:
                node = self.nodes.get(edge.target)
                if node is not None:
                    children.append(node)
        return children

    def _traverse(self, sha256: str, *, direction: str) -> list[Node]:
        visited: set[str] = set()
        emitted: set[str] = set()
        result: list[Node] = []
        stack = [sha256]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            neighbours = (
                self._direct_parents(current)
                if direction == "up"
                else self._direct_children(current)
            )
            for n in neighbours:
                if n.sha256 in emitted:
                    continue
                emitted.add(n.sha256)
                result.append(n)
                stack.append(n.sha256)
        return sorted(result, key=_node_sort_key)


def _node_sort_key(n: Node) -> tuple[int, str, str]:
    return (_STAGE_ORDER.get(n.stage, 99), n.id, n.sha256)


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _extract_output_sha(artifact: dict[str, Any]) -> str | None:
    out = artifact.get("output")
    if isinstance(out, dict):
        sha = out.get("sha256")
        if isinstance(sha, str) and sha:
            return sha
    return None


def _extract_output_path(artifact: dict[str, Any]) -> str:
    out = artifact.get("output")
    if isinstance(out, dict):
        return str(out.get("path", ""))
    return ""


def _extract_source_edge(data: dict[str, Any], target_sha: str) -> Edge | None:
    """Extract a source→target edge from a sidecar's ``source`` field."""
    source = data.get("source")
    if isinstance(source, dict):
        source_sha = source.get("sha256")
        if isinstance(source_sha, str) and source_sha:
            return Edge(source=source_sha, target=target_sha)
    return None


def _ingest_clips(index: LineageIndex, files: list[Path]) -> None:
    for path in files:
        data = _load_json(path)
        if data is None:
            index.warnings.append(f"malformed sidecar: {path}")
            continue
        sha = _extract_output_sha(data)
        clip_id = data.get("clip_id")
        if not sha or not clip_id:
            index.warnings.append(f"missing sha256 or clip_id: {path}")
            continue
        index.nodes[sha] = Node(
            id=clip_id,
            stage="ingest",
            sha256=sha,
            path=_extract_output_path(data),
            sidecar=str(path),
        )


def _ingest_views(index: LineageIndex, files: list[Path]) -> None:
    for path in files:
        data = _load_json(path)
        if data is None:
            index.warnings.append(f"malformed sidecar: {path}")
            continue
        sha = _extract_output_sha(data)
        view_id = data.get("view_id")
        if not sha or not view_id:
            index.warnings.append(f"missing sha256 or view_id: {path}")
            continue
        index.nodes[sha] = Node(
            id=view_id,
            stage="crop",
            sha256=sha,
            path=_extract_output_path(data),
            sidecar=str(path),
        )
        edge = _extract_source_edge(data, sha)
        if edge is not None:
            index.edges.append(edge)


def _ingest_optimized(index: LineageIndex, files: list[Path]) -> None:
    for path in files:
        data = _load_json(path)
        if data is None:
            index.warnings.append(f"malformed sidecar: {path}")
            continue
        sha = _extract_output_sha(data)
        opt_id = data.get("optimized_id")
        if not sha or not opt_id:
            index.warnings.append(f"missing sha256 or optimized_id: {path}")
            continue
        index.nodes[sha] = Node(
            id=opt_id,
            stage="optimize",
            sha256=sha,
            path=_extract_output_path(data),
            sidecar=str(path),
        )
        edge = _extract_source_edge(data, sha)
        if edge is not None:
            index.edges.append(edge)


def build_index(*dirs: Path) -> LineageIndex:
    """Scan one or more directories (recursively) for provenance sidecars and build a lineage index.

    Recognised sidecar patterns:
    - ``*.cosmos_clip.v1.json``  → ingest stage
    - ``*.cosmos_view.v1.json``  → crop stage
    - ``*.cosmos_optimized.v1.json`` → optimize stage
    """
    index = LineageIndex()

    clip_files: list[Path] = []
    view_files: list[Path] = []
    optimized_files: list[Path] = []

    for d in dirs:
        if not d.is_dir():
            index.warnings.append(f"skipped non-directory: {d}")
            continue
        clip_files.extend(sorted(d.rglob("*.cosmos_clip.v1.json")))
        view_files.extend(sorted(d.rglob("*.cosmos_view.v1.json")))
        optimized_files.extend(sorted(d.rglob("*.cosmos_optimized.v1.json")))

    _ingest_clips(index, clip_files)
    _ingest_views(index, view_files)
    _ingest_optimized(index, optimized_files)

    return index
