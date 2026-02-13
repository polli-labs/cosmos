from __future__ import annotations

from pathlib import Path
from typing import Annotated

import questionary
import typer

from cosmos.sdk.ingest import IngestOptions, ingest

app = typer.Typer(help="COSM camera MP4 generation (ingest)")


@app.command()
def run(
    input_dir: Annotated[Path | None, typer.Option(exists=True, dir_okay=True)] = None,
    output_dir: Annotated[Path | None, typer.Option(dir_okay=True)] = None,
    non_interactive: Annotated[
        bool, typer.Option("--yes", help="Skip interactive prompts")
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
) -> None:
    """Run interactive or non-interactive ingest."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and not non_interactive)
    if not non_interactive:
        if input_dir is None:
            selected = questionary.path("Select input directory:").ask() or "."
            input_dir = Path(selected)
        if output_dir is None:
            selected = questionary.path("Select output directory:").ask() or "."
            output_dir = Path(selected)
    if input_dir is None or output_dir is None:
        raise typer.BadParameter("Both input and output directories are required")

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
    for p in results:
        typer.echo(str(p))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
