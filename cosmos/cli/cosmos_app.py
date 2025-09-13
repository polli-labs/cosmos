from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cosmos.cli.crop_cli import app as crop_app
from cosmos.cli.ingest_cli import app as ingest_app
from cosmos.sdk.crop import CropJob
from cosmos.sdk.crop import crop as sdk_crop
from cosmos.sdk.ingest import IngestOptions
from cosmos.sdk.ingest import ingest as sdk_ingest

app = typer.Typer(help="Cosmos: ingest + crop toolkit")
app.add_typer(ingest_app, name="ingest", help="COSM camera MP4 generation")
app.add_typer(crop_app, name="crop", help="Post-processing square crop")


@app.command()
def pipeline(
    input_dir: Annotated[
        Path, typer.Argument(..., exists=True, file_okay=False, help="Raw input directory")
    ],
    output_dir: Annotated[Path, typer.Argument(..., help="Output directory")],
    post_process: Annotated[
        bool, typer.Option("--post-process/--no-post-process", help="Run crop after ingest")
    ] = False,
    crop_config: Annotated[
        Path | None,
        typer.Option("--crop-config", exists=True, file_okay=True, help="Optional crop jobs JSON"),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Build commands; do not execute")
    ] = False,
    clip: Annotated[
        list[str] | None, typer.Option("--clip", help="Only process these clip names (repeatable)")
    ] = None,
) -> None:
    """Convenience pipeline: ingest → optional crop."""
    opts = IngestOptions(dry_run=dry_run, clips=clip)
    videos = sdk_ingest(input_dir, output_dir, manifest=None, options=opts)
    typer.echo(f"Ingest produced {len(videos)} files")

    if post_process:
        jobs: list[CropJob]
        if crop_config and crop_config.exists():
            from cosmos.crop.jobs import parse_jobs_json
            jobs = parse_jobs_json(crop_config)
        else:
            jobs = [CropJob()]
        out = sdk_crop(videos, jobs, output_dir, ffmpeg_opts={"dry_run": dry_run})
        typer.echo(f"Crop produced {len(out)} files")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
