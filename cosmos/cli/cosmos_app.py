from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, cast

import typer

from cosmos.cli.crop_cli import app as crop_app
from cosmos.cli.ingest_cli import app as ingest_app
from cosmos.cli.io import (
    can_prompt,
    emit_paths,
    emit_payload,
    info,
    raise_mapped_exit,
    resolve_output_mode,
)
from cosmos.cli.lineage_cli import app as lineage_app
from cosmos.cli.optimize_cli import app as optimize_app
from cosmos.cli.provenance_cli import app as prov_app
from cosmos.crop.squarecrop import SquareCropSpec, build_crop_filter
from cosmos.ffmpeg.args import build_square_crop_args
from cosmos.sdk.crop import CropJob
from cosmos.sdk.crop import crop as sdk_crop
from cosmos.sdk.crop import validate_jobs as validate_crop_jobs
from cosmos.sdk.dry_run import (
    build_dry_run_plan,
    command_declaration,
    input_declaration,
    output_declaration,
    write_dry_run_plan,
)
from cosmos.sdk.ingest import IngestOptions
from cosmos.sdk.ingest import ingest as sdk_ingest
from cosmos.sdk.profiles import resolve_profile

app = typer.Typer(help="Cosmos: ingest + crop + optimize toolkit")
app.add_typer(ingest_app, name="ingest", help="Video ingest (auto-detects source layout)")
app.add_typer(crop_app, name="crop", help="Post-processing crop (square or rectangular)")
app.add_typer(optimize_app, name="optimize", help="Web-ready MP4 optimization")
app.add_typer(prov_app, name="provenance", help="Inspect provenance artifacts")
app.add_typer(lineage_app, name="lineage", help="Lineage graph queries")


def _load_plan(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]


def _plan_process_crop_stage(
    videos: list[Path],
    jobs: Sequence[object],
    output_dir: Path,
    *,
    profile: str | None,
) -> tuple[list[Path], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    profile_obj = resolve_profile(profile)
    encoder = (
        profile_obj.pinned_encoder if profile_obj and profile_obj.pinned_encoder else "libx264"
    )
    threads = profile_obj.threads if profile_obj else None
    bitexact = profile_obj.bitexact if profile_obj else False

    outputs: list[Path] = []
    output_declarations: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []
    validation: list[dict[str, object]] = []

    validate_crop_jobs(list(jobs))

    if all(isinstance(job, CropJob) for job in jobs):
        square_jobs = [job for job in jobs if isinstance(job, CropJob)] or [CropJob()]
        for vi, src in enumerate(videos):
            for ji, job in enumerate(square_jobs):
                spec = SquareCropSpec(
                    size=job.size,
                    center_x=job.center_x,
                    center_y=job.center_y,
                    offset_x=job.offset_x,
                    offset_y=job.offset_y,
                    start=job.start,
                    end=job.end,
                )
                out = output_dir / f"crop_{vi:03d}_job{ji:02d}_t00_s{spec.size}.mp4"
                argv = build_square_crop_args(
                    src,
                    out,
                    encoder=encoder,
                    crop_filter=build_crop_filter(spec),
                    start=spec.start,
                    end=spec.end,
                    threads=threads,
                    bitexact=bitexact,
                )
                outputs.append(out)
                output_declarations.append(
                    output_declaration(
                        out,
                        kind="video",
                        stage="crop",
                        exists=False,
                    )
                )
                commands.append(
                    command_declaration(
                        stage="crop",
                        name=f"job{ji}",
                        argv=argv,
                        inputs=[src],
                        outputs=[out],
                    )
                )
        return outputs, output_declarations, commands, validation

    for vi, src in enumerate(videos):
        for ji, job in enumerate(jobs):
            view_id = getattr(job, "view_id", None)
            out_name = f"{view_id}.mp4" if view_id else f"crop_{vi:03d}_rect{ji:02d}.mp4"
            out = output_dir / out_name
            outputs.append(out)
            output_declarations.append(
                output_declaration(
                    out,
                    kind="video",
                    stage="crop",
                    exists=False,
                )
            )
            validation.append(
                {
                    "level": "warning",
                    "stage": "crop",
                    "input": str(src),
                    "output": str(out),
                    "message": (
                        "process dry-run declared this rect crop output from a planned "
                        "ingest artifact; executable rect argv requires source dimensions "
                        "available after ingest. Run `cosmos crop run --dry-run --json` "
                        "against materialized inputs for rect command argv."
                    ),
                }
            )
    return outputs, output_declarations, commands, validation


def _run_process(  # noqa: C901
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
    profile: str | None = None,
    non_interactive: bool = False,
    skip_ffmpeg_check: bool = False,
) -> None:
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    try:
        opts = IngestOptions(dry_run=dry_run, clips=clip, profile=profile)
        videos = sdk_ingest(input_dir, output_dir, manifest=None, options=opts)
        outputs = videos
        crop_outputs: list[Path] = []
        process_plan_path = output_dir / "cosmos_process_dry_run.v1.json"
        ingest_run_path = output_dir / "cosmos_ingest_run.v1.json"
        ingest_plan_path = output_dir / "cosmos_ingest_dry_run.v1.json"
        process_output_declarations: list[dict[str, object]] = []
        process_commands: list[dict[str, object]] = []
        process_validation: list[dict[str, object]] = []

        if dry_run:
            ingest_plan = _load_plan(ingest_plan_path)
            ingest_outputs = ingest_plan.get("outputs")
            ingest_commands = ingest_plan.get("commands")
            process_output_declarations.extend(_dict_list(ingest_outputs))
            process_commands.extend(_dict_list(ingest_commands))

        if post_process:
            if crop_config and crop_config.exists():
                from cosmos.crop.jobs import parse_jobs_json

                parsed_jobs = parse_jobs_json(crop_config)
            else:
                parsed_jobs = [CropJob()]
            if dry_run:
                (
                    crop_outputs,
                    crop_declarations,
                    crop_commands,
                    crop_validation,
                ) = _plan_process_crop_stage(
                    videos,
                    parsed_jobs,
                    output_dir,
                    profile=profile,
                )
                process_output_declarations = crop_declarations
                process_commands.extend(crop_commands)
                process_validation.extend(crop_validation)
            else:
                crop_outputs = sdk_crop(
                    videos,
                    parsed_jobs,
                    output_dir,
                    ffmpeg_opts={"dry_run": dry_run, "profile": profile},
                )
            outputs = crop_outputs

        if dry_run:
            if not post_process and not process_output_declarations:
                process_output_declarations = [
                    output_declaration(p, kind="video", stage="ingest") for p in outputs
                ]
            process_plan = build_dry_run_plan(
                command="cosmos process",
                inputs=[input_declaration(input_dir, kind="directory", stage="process")],
                outputs=process_output_declarations,
                commands=process_commands,
                metadata_writes=[ingest_run_path, ingest_plan_path, process_plan_path],
                validation=process_validation,
                extra={
                    "stages": {
                        "ingest": {
                            "run_artifact": str(ingest_run_path),
                            "dry_run_plan": str(ingest_plan_path),
                            "outputs": [str(p) for p in videos],
                        },
                        "crop": {
                            "enabled": post_process,
                            "outputs": [str(p) for p in crop_outputs],
                        },
                    }
                },
            )
            write_dry_run_plan(process_plan_path, process_plan)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    if output_mode == "json":
        payload: dict[str, object] = {
            "command": "cosmos process",
            "dry_run": dry_run,
            "post_process": post_process,
            "count": len(outputs),
            "ingest_count": len(videos),
            "crop_count": len(crop_outputs),
            "ingest_outputs": [str(p) for p in videos],
            "crop_outputs": [str(p) for p in crop_outputs],
            "outputs": [str(p) for p in outputs],
        }
        if dry_run:
            payload["run_artifact"] = str(output_dir / "cosmos_ingest_run.v1.json")
            payload["dry_run_plan"] = str(output_dir / "cosmos_process_dry_run.v1.json")
            payload["stage_artifacts"] = {
                "ingest": {
                    "run_artifact": str(output_dir / "cosmos_ingest_run.v1.json"),
                    "dry_run_plan": str(output_dir / "cosmos_ingest_dry_run.v1.json"),
                },
                "process": {
                    "dry_run_plan": str(output_dir / "cosmos_process_dry_run.v1.json"),
                },
            }
            payload["output_declarations"] = [
                output_declaration(
                    p,
                    kind="video",
                    stage="crop" if post_process else "ingest",
                    exists=False,
                )
                for p in outputs
            ]
        emit_payload(payload, mode=output_mode)
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
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="Determinism profile (strict|balanced|throughput). "
            "Controls encoder, threads, and bitexact flags for reproducibility.",
        ),
    ] = None,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-input", help="Skip interactive prompts")
    ] = False,
    skip_ffmpeg_check: Annotated[
        bool,
        typer.Option(
            "--skip-ffmpeg-check",
            help="Skip the NVENC ffmpeg bootstrap check (for CI/headless use).",
        ),
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
        profile=profile,
        non_interactive=non_interactive,
        skip_ffmpeg_check=skip_ffmpeg_check,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
