from __future__ import annotations

from pathlib import Path
from typing import Annotated

import questionary
import typer

from cosmos.sdk.crop import CropJob, crop

app = typer.Typer(help="Square crop post-processing")


@app.command()
def run(
    input_videos: Annotated[
        list[Path] | None,
        typer.Option("--input", help="One or more input MP4s", exists=True, show_default=False),
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option(dir_okay=True, help="Directory for outputs")
    ] = None,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-tui", help="Skip interactive prompts (agent mode)")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Build commands; do not execute")
    ] = False,
    jobs_file: Annotated[
        Path | None,
        typer.Option(
            "--jobs-file", exists=True, help="Squarecrop jobs JSON (offsets/targets/trims)"
        ),
    ] = None,
    size: Annotated[
        int, typer.Option(help="Square target size (pixels) when not using --jobs-file")
    ] = 1080,
    offset_x: Annotated[
        float | None,
        typer.Option(
            help="Margin-relative horizontal offset [-1,1]. 0=center, +right, -left. Cannot be combined with centers."
        ),
    ] = None,
    offset_y: Annotated[
        float | None,
        typer.Option(
            help="Margin-relative vertical offset [-1,1]. 0=center, +down, -up. Cannot be combined with centers."
        ),
    ] = None,
    center_x: Annotated[
        float | None,
        typer.Option(
            help="Absolute center X in [0,1] of full frame (use when offsets are not set)."
        ),
    ] = None,
    center_y: Annotated[
        float | None,
        typer.Option(
            help="Absolute center Y in [0,1] of full frame (use when offsets are not set)."
        ),
    ] = None,
    trim_start: Annotated[
        float | None,
        typer.Option(help="Optional trim start in seconds (time-based)."),
    ] = None,
    trim_end: Annotated[
        float | None,
        typer.Option(help="Optional trim end in seconds (time-based)."),
    ] = None,
) -> None:
    """Run square crop in interactive or agent (non-interactive) mode."""
    videos: list[Path] = input_videos or []
    if not non_interactive and not videos:
        sel = questionary.text("Enter comma-separated MP4 paths:").ask() or ""
        videos = [Path(s.strip()) for s in sel.split(",") if s.strip()]
    if not non_interactive and out_dir is None:
        selected = questionary.path("Select output directory:").ask() or "."
        out_dir = Path(selected)
    if out_dir is None:
        raise typer.BadParameter("Output directory is required")

    # Default jobs or parse from file
    if jobs_file:
        from cosmos.crop.jobs import parse_jobs_json

        jobs = parse_jobs_json(jobs_file)
    else:
        jobs = [
            CropJob(
                center_x=center_x,
                center_y=center_y,
                offset_x=offset_x,
                offset_y=offset_y,
                size=size,
                start=trim_start,
                end=trim_end,
            )
        ]
    results = crop(videos, jobs, out_dir, ffmpeg_opts={"dry_run": dry_run})
    for p in results:
        typer.echo(str(p))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
