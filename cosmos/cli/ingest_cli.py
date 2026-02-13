from __future__ import annotations

from pathlib import Path
from typing import Annotated

import questionary
import typer

from cosmos.cli.io import (
    can_prompt,
    emit_paths,
    emit_payload,
    raise_mapped_exit,
    resolve_output_mode,
)
from cosmos.sdk.ingest import IngestOptions, ingest

app = typer.Typer(help="COSM camera MP4 generation (ingest)")


@app.command()
def run(
    input_dir: Annotated[Path | None, typer.Option(exists=True, dir_okay=True)] = None,
    output_dir: Annotated[Path | None, typer.Option(dir_okay=True)] = None,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-input", help="Skip interactive prompts")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Build commands; do not execute")
    ] = False,
    clips: Annotated[
        list[str] | None, typer.Option("--clip", help="Only process these clip names (repeatable)")
    ] = None,
    scale_filter: Annotated[
        str | None,
        typer.Option("--scale-filter", help="scale filter (lanczos|bicubic|spline36|bilinear)"),
    ] = None,
    filter_threads: Annotated[
        int | None, typer.Option("--filter-threads", help="-filter_threads")
    ] = None,
    filter_complex_threads: Annotated[
        int | None, typer.Option("--fc-threads", help="-filter_complex_threads")
    ] = None,
    decode: Annotated[str, typer.Option("--decode", help="decode mode: auto|hw|sw")] = "auto",
    window_seconds: Annotated[
        float | None, typer.Option("--window", help="Process only first N seconds")
    ] = None,
    skip_ffmpeg_check: Annotated[
        bool,
        typer.Option(
            "--skip-ffmpeg-check",
            help="Skip the NVENC ffmpeg bootstrap check (for CI/headless use).",
        ),
    ] = False,
    json_out: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON to stdout")
    ] = False,
    plain_out: Annotated[
        bool, typer.Option("--plain", help="Emit plain line-based output to stdout")
    ] = False,
) -> None:
    """Run interactive or non-interactive ingest."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    if prompt_allowed:
        if input_dir is None:
            selected = questionary.path("Select input directory:").ask() or "."
            input_dir = Path(selected)
        if output_dir is None:
            selected = questionary.path("Select output directory:").ask() or "."
            output_dir = Path(selected)
    if input_dir is None or output_dir is None:
        raise typer.BadParameter(
            "Both input and output directories are required (set --yes/--no-input for non-interactive runs)."
        )

    try:
        options = IngestOptions(
            dry_run=dry_run,
            clips=clips,
            scale_filter=scale_filter,
            filter_threads=filter_threads,
            filter_complex_threads=filter_complex_threads,
            decode=decode,
            window_seconds=window_seconds,
        )
        results = ingest(input_dir, output_dir, manifest=None, options=options)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos ingest run",
                "dry_run": dry_run,
                "count": len(results),
                "outputs": [str(p) for p in results],
            },
            mode=output_mode,
        )
        return

    emit_paths(results, mode=output_mode)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
