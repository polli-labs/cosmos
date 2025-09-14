# ruff: noqa: I001
from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Annotated

import typer

from cosmos.sdk.provenance import find_clip_for_file
from cosmos.sdk.provenance import find_view_for_file
from cosmos.sdk.provenance import list_clip_artifacts
from cosmos.sdk.provenance import list_view_artifacts
from cosmos.sdk.provenance import map_artifacts_by_sha
from cosmos.sdk.provenance import sha256_file


app = typer.Typer(help="Inspect provenance artifacts emitted by Cosmos (ingest/crop)")


@app.command("sha")
def cmd_sha(path: Annotated[Path, typer.Argument(exists=True)]):
    """Compute sha256 of a file."""
    typer.echo(sha256_file(path))


@app.command("list")
def cmd_list(
    dir_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    kind: Annotated[str, typer.Option("--kind", help="clip|view|all")] = "all",
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON lines")]= False,
):
    """List provenance artifacts under a directory."""
    items: list[dict] = []
    if kind in ("clip", "all"):
        for p in list_clip_artifacts(dir_path):
            p["_kind"] = "clip"
            items.append(p)
    if kind in ("view", "all"):
        for p in list_view_artifacts(dir_path):
            p["_kind"] = "view"
            items.append(p)
    if json_out:
        for obj in items:
            typer.echo(json.dumps(obj))
    else:
        for obj in items:
            kind = obj.get("_kind")
            out = obj.get("output", {})
            typer.echo(f"{kind}: {out.get('path')} sha256={out.get('sha256')}")


@app.command("clip-of")
def cmd_clip_of(
    file_path: Annotated[Path, typer.Argument(exists=True, help="Output MP4 path from ingest")],
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON")]= False,
):
    """Find the clip artifact JSON for an ingest-produced MP4 by hashing the file."""
    meta = find_clip_for_file(file_path)
    if not meta:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(meta, indent=2) if json_out else (meta.get("output", {}).get("path") or ""))


@app.command("view-of")
def cmd_view_of(
    file_path: Annotated[Path, typer.Argument(exists=True, help="Output MP4 path from squarecrop")],
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON")]= False,
):
    """Find the view artifact JSON for a squarecrop-produced MP4 by hashing the file."""
    meta = find_view_for_file(file_path)
    if not meta:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(meta, indent=2) if json_out else (meta.get("output", {}).get("path") or ""))


@app.command("views-for-clip")
def cmd_views_for_clip(
    clip_file: Annotated[Path, typer.Argument(exists=True, help="Ingest MP4 path (source for views)")],
    search_dir: Annotated[list[Path] | None, typer.Option("--in", exists=True, file_okay=False, help="Directories to search for view artifacts (repeatable)")]= None,
):
    """List crop view artifacts that reference the given clip's output sha (source.sha256)."""
    from cosmos.sdk.provenance import list_view_artifacts

    sha = sha256_file(clip_file)
    dirs: Iterable[Path] = search_dir or [clip_file.parent]
    count = 0
    for d in dirs:
        for meta in list_view_artifacts(d):
            src = meta.get("source") or {}
            if src.get("sha256") == sha:
                count += 1
                typer.echo(meta.get("output", {}).get("path") or json.dumps(meta))
    if count == 0:
        raise typer.Exit(code=1)


@app.command("map")
def cmd_map(dir_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)],):
    """Emit mapping from output sha256 → artifact JSON path (clip + view)."""
    # Start from computed mapping and enrich with file paths when possible
    result: dict[str, dict] = map_artifacts_by_sha(dir_path).copy()
    for p in dir_path.glob("*.cosmos_*.v1.json"):
        try:
            obj = json.loads(p.read_text())
            sha = ((obj.get("output") or {}).get("sha256"))
            if isinstance(sha, str):
                obj["_path"] = str(p)
                base = result.get(sha, {})
                base.update(obj)
                result[sha] = base
        except Exception as e:
            typer.secho(f"warn: failed to read {p.name}: {e}", err=True)
    typer.echo(json.dumps(result, indent=2))
