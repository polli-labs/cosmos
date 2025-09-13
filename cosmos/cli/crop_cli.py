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
        list[Path] | None, typer.Option("--input", help="One or more input MP4s", exists=True)
    ] = None,
    out_dir: Annotated[Path | None, typer.Option(dir_okay=True)] = None,
    non_interactive: Annotated[bool, typer.Option("--yes", help="Skip interactive prompts")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Build commands; do not execute")] = False,
    jobs_file: Annotated[Path | None, typer.Option("--jobs-file", exists=True, help="Squarecrop jobs JSON (offsets/targets/trims)")] = None,
) -> None:
    """Run interactive or non-interactive square cropping."""
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
        jobs = [CropJob()]
    results = crop(videos, jobs, out_dir, ffmpeg_opts={"dry_run": dry_run})
    for p in results:
        typer.echo(str(p))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
