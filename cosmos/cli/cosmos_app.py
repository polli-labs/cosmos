from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cosmos.cli.crop_cli import app as crop_app
from cosmos.cli.ingest_cli import app as ingest_app
from cosmos.cli.io import emit_paths, emit_payload, info, raise_mapped_exit, resolve_output_mode
from cosmos.cli.optimize_cli import app as optimize_app
from cosmos.cli.provenance_cli import app as prov_app
from cosmos.sdk.crop import CropJob
from cosmos.sdk.crop import crop as sdk_crop
from cosmos.sdk.ingest import IngestOptions
from cosmos.sdk.ingest import ingest as sdk_ingest

app = typer.Typer(help="Cosmos: ingest + crop + optimize toolkit")
app.add_typer(ingest_app, name="ingest", help="Video ingest (auto-detects source layout)")
app.add_typer(crop_app, name="crop", help="Post-processing crop (square or rectangular)")
app.add_typer(optimize_app, name="optimize", help="Web-ready MP4 optimization")
app.add_typer(prov_app, name="provenance", help="Inspect provenance artifacts")


def _run_process(
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
    json_out: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON to stdout")
    ] = False,
    plain_out: Annotated[
        bool, typer.Option("--plain", help="Emit plain line-based output to stdout")
    ] = False,
    deprecated_alias: bool = False,
) -> None:
    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    if deprecated_alias:
        info("`cosmos pipeline` is deprecated; use `cosmos process` instead.")

    try:
        opts = IngestOptions(dry_run=dry_run, clips=clip)
        videos = sdk_ingest(input_dir, output_dir, manifest=None, options=opts)
        outputs = videos
        crop_outputs: list[Path] = []

        if post_process:
            if crop_config and crop_config.exists():
                from cosmos.crop.jobs import parse_jobs_json

                parsed_jobs = parse_jobs_json(crop_config)
            else:
                parsed_jobs = [CropJob()]
            crop_outputs = sdk_crop(
                videos, parsed_jobs, output_dir, ffmpeg_opts={"dry_run": dry_run}
            )
            outputs = crop_outputs
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos process",
                "dry_run": dry_run,
                "post_process": post_process,
                "ingest_count": len(videos),
                "crop_count": len(crop_outputs),
                "ingest_outputs": [str(p) for p in videos],
                "crop_outputs": [str(p) for p in crop_outputs],
                "outputs": [str(p) for p in outputs],
            },
            mode=output_mode,
        )
        return

    if output_mode == "human":
        info(f"Ingest produced {len(videos)} files")
        if post_process:
            info(f"Crop produced {len(crop_outputs)} files")
    emit_paths(outputs, mode=output_mode)


@app.command()
def process(
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
    json_out: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON to stdout")
    ] = False,
    plain_out: Annotated[
        bool, typer.Option("--plain", help="Emit plain line-based output to stdout")
    ] = False,
) -> None:
    """Canonical ingest -> optional crop workflow."""
    _run_process(
        input_dir=input_dir,
        output_dir=output_dir,
        post_process=post_process,
        crop_config=crop_config,
        dry_run=dry_run,
        clip=clip,
        json_out=json_out,
        plain_out=plain_out,
    )


@app.command(hidden=True)
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
    json_out: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON to stdout")
    ] = False,
    plain_out: Annotated[
        bool, typer.Option("--plain", help="Emit plain line-based output to stdout")
    ] = False,
) -> None:
    """Deprecated alias for process."""
    _run_process(
        input_dir=input_dir,
        output_dir=output_dir,
        post_process=post_process,
        crop_config=crop_config,
        dry_run=dry_run,
        clip=clip,
        json_out=json_out,
        plain_out=plain_out,
        deprecated_alias=True,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
