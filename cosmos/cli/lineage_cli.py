"""CLI surfaces for lineage graph queries.

Subcommands live under ``cosmos lineage`` and provide upstream/downstream
traversal, full chain views, and index (re)generation from provenance
sidecar artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from cosmos.cli.io import ExitCode, emit_payload, fail, info, resolve_output_mode
from cosmos.sdk.lineage import LineageIndex, Node, build_index

app = typer.Typer(help="Lineage graph queries over provenance artifacts")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_or_build(dirs: list[Path]) -> LineageIndex:
    """Build a lineage index from the provided directories."""
    return build_index(*dirs)


def _resolve_node(index: LineageIndex, identifier: str) -> tuple[Node | None, str | None]:
    """Resolve a node by sha256 (prefix match) or artifact ID.

    Returns ``(node, error_message)`` where ``error_message`` is set for
    actionable resolution failures (for example ambiguous SHA prefixes).
    """
    # exact sha256 match
    if identifier in index.nodes:
        return index.nodes[identifier], None

    # sha256 prefix match
    prefix_matches = [n for sha, n in index.nodes.items() if sha.startswith(identifier)]
    if len(prefix_matches) == 1:
        return prefix_matches[0], None
    if len(prefix_matches) > 1:
        sample = ", ".join(n.sha256[:12] for n in prefix_matches[:5])
        return (
            None,
            f"ambiguous artifact identifier: {identifier!r}; "
            f"matches {len(prefix_matches)} artifacts ({sample})",
        )

    # artifact ID match (e.g., clip-CLIP1-abc12345)
    for node in index.nodes.values():
        if node.id == identifier:
            return node, None

    return None, None


def _nodes_payload(nodes: list[Node]) -> list[dict[str, str]]:
    return [n.to_dict() for n in nodes]


def _emit_nodes(
    nodes: list[Node],
    *,
    mode: str,
    label: str,
    root: Node | None = None,
) -> None:
    if mode == "json":
        payload: dict[str, Any] = {"command": f"cosmos lineage {label}", "count": len(nodes)}
        if root is not None:
            payload["root"] = root.to_dict()
        payload["results"] = _nodes_payload(nodes)
        emit_payload(payload, mode=mode)
        return

    if mode == "human":
        if root is not None:
            info(f"{label} of {root.id} ({root.stage}, sha={root.sha256[:12]}…)")
        info(f"{len(nodes)} artifact(s)")

    for n in nodes:
        if mode == "plain":
            typer.echo(f"{n.sha256}\t{n.stage}\t{n.id}")
        else:
            typer.echo(f"  {n.stage:10s}  {n.id}  sha={n.sha256[:12]}…  {n.path}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def build(
    dirs: Annotated[
        list[Path],
        typer.Argument(exists=True, file_okay=False, help="Directories to scan for sidecars"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write index JSON to this path"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Emit index as JSON to stdout")] = False,
    plain_out: Annotated[
        bool, typer.Option("--plain", help="Emit plain summary to stdout")
    ] = False,
) -> None:
    """Build a lineage index from provenance sidecars in the given directories."""
    mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    index = build_index(*dirs)

    if output is not None:
        written = index.write(output)
        if mode == "human":
            info(
                f"Wrote lineage index ({len(index.nodes)} nodes, {len(index.edges)} edges) → {written}"
            )
    if index.warnings and mode == "human":
        for w in index.warnings:
            info(f"  warn: {w}")

    payload = index.to_dict()
    payload["command"] = "cosmos lineage build"
    if output is not None:
        payload["output"] = str(output)

    if mode == "json":
        emit_payload(payload, mode=mode)
    elif mode == "plain":
        typer.echo(f"{payload['node_count']}\t{payload['edge_count']}")


@app.command()
def upstream(
    identifier: Annotated[str, typer.Argument(help="Artifact sha256 (or prefix) or ID")],
    dirs: Annotated[
        list[Path],
        typer.Option("--in", exists=True, file_okay=False, help="Directories to scan"),
    ] = [],  # noqa: B006 — typer requires mutable default
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout")] = False,
    plain_out: Annotated[bool, typer.Option("--plain", help="Emit plain output to stdout")] = False,
) -> None:
    """Show upstream ancestors of an artifact."""
    mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    scan_dirs = dirs if dirs else [Path.cwd()]
    index = _load_or_build(scan_dirs)
    node, resolution_error = _resolve_node(index, identifier)
    if node is None:
        fail(
            resolution_error or f"artifact not found: {identifier}",
            code=ExitCode.INPUT_VALIDATION_ERROR,
        )
        return  # unreachable but keeps mypy happy
    results = index.upstream(node.sha256)
    _emit_nodes(results, mode=mode, label="upstream", root=node)


@app.command()
def downstream(
    identifier: Annotated[str, typer.Argument(help="Artifact sha256 (or prefix) or ID")],
    dirs: Annotated[
        list[Path],
        typer.Option("--in", exists=True, file_okay=False, help="Directories to scan"),
    ] = [],  # noqa: B006
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout")] = False,
    plain_out: Annotated[bool, typer.Option("--plain", help="Emit plain output to stdout")] = False,
) -> None:
    """Show downstream derivatives of an artifact."""
    mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    scan_dirs = dirs if dirs else [Path.cwd()]
    index = _load_or_build(scan_dirs)
    node, resolution_error = _resolve_node(index, identifier)
    if node is None:
        fail(
            resolution_error or f"artifact not found: {identifier}",
            code=ExitCode.INPUT_VALIDATION_ERROR,
        )
        return
    results = index.downstream(node.sha256)
    _emit_nodes(results, mode=mode, label="downstream", root=node)


@app.command("chain")
def cmd_chain(
    identifier: Annotated[str, typer.Argument(help="Artifact sha256 (or prefix) or ID")],
    dirs: Annotated[
        list[Path],
        typer.Option("--in", exists=True, file_okay=False, help="Directories to scan"),
    ] = [],  # noqa: B006
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout")] = False,
    plain_out: Annotated[bool, typer.Option("--plain", help="Emit plain output to stdout")] = False,
) -> None:
    """Show the full lineage chain (upstream + self + downstream)."""
    mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    scan_dirs = dirs if dirs else [Path.cwd()]
    index = _load_or_build(scan_dirs)
    node, resolution_error = _resolve_node(index, identifier)
    if node is None:
        fail(
            resolution_error or f"artifact not found: {identifier}",
            code=ExitCode.INPUT_VALIDATION_ERROR,
        )
        return
    results = index.chain(node.sha256)
    _emit_nodes(results, mode=mode, label="chain", root=node)


@app.command("tree")
def cmd_tree(
    identifier: Annotated[str, typer.Argument(help="Artifact sha256 (or prefix) or ID")],
    dirs: Annotated[
        list[Path],
        typer.Option("--in", exists=True, file_okay=False, help="Directories to scan"),
    ] = [],  # noqa: B006
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout")] = False,
    plain_out: Annotated[bool, typer.Option("--plain", help="Emit plain output to stdout")] = False,
) -> None:
    """Show the upstream tree for an artifact (nested source hierarchy)."""
    mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    scan_dirs = dirs if dirs else [Path.cwd()]
    index = _load_or_build(scan_dirs)
    node, resolution_error = _resolve_node(index, identifier)
    if node is None:
        fail(
            resolution_error or f"artifact not found: {identifier}",
            code=ExitCode.INPUT_VALIDATION_ERROR,
        )
        return

    tree_data = index.tree(node.sha256)

    if mode == "json":
        payload: dict[str, Any] = {"command": "cosmos lineage tree"}
        payload["tree"] = tree_data
        emit_payload(payload, mode=mode)
        return

    _print_tree(tree_data, mode=mode)


def _print_tree(tree: dict[str, Any], *, mode: str, indent: int = 0) -> None:
    if not tree:
        return
    prefix = "  " * indent
    stage = tree.get("stage", "?")
    aid = tree.get("id", "?")
    sha = tree.get("sha256", "?")
    path = tree.get("path", "")

    if mode == "plain":
        typer.echo(f"{prefix}{sha}\t{stage}\t{aid}")
    else:
        typer.echo(f"{prefix}{stage:10s}  {aid}  sha={sha[:12]}…  {path}")

    for source in tree.get("sources", []):
        _print_tree(source, mode=mode, indent=indent + 1)
