from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import questionary
import typer

from cosmos.cli.io import (
    can_prompt,
    emit_paths,
    emit_payload,
    info,
    raise_mapped_exit,
    resolve_output_mode,
)
from cosmos.sdk.optimize import OptimizeMode, OptimizeOptions, optimize

app = typer.Typer(help="Web-ready MP4 optimization (faststart/remux/transcode)")


def _resolve_io(
    *,
    input_videos: list[Path] | None,
    out_dir: Path | None,
    prompt_allowed: bool,
) -> tuple[list[Path], Path]:
    resolved_inputs = list(input_videos or [])
    resolved_out_dir = out_dir

    if prompt_allowed:
        if not resolved_inputs:
            selected = questionary.text("Enter comma-separated MP4 paths:").ask() or ""
            resolved_inputs = [Path(s.strip()) for s in selected.split(",") if s.strip()]
        if resolved_out_dir is None:
            selected = questionary.path("Select output directory:").ask() or "."
            resolved_out_dir = Path(selected)

    if not resolved_inputs:
        raise typer.BadParameter(
            "At least one --input is required (set --yes/--no-input for non-interactive runs)."
        )
    if resolved_out_dir is None:
        raise typer.BadParameter(
            "Output directory is required (set --yes/--no-input for non-interactive runs)."
        )

    return resolved_inputs, resolved_out_dir


def _normalize_mode(mode: str) -> OptimizeMode:
    normalized = mode.strip().lower()
    if normalized not in {"auto", "remux", "transcode"}:
        raise typer.BadParameter("mode must be one of: auto, remux, transcode")
    return cast(OptimizeMode, normalized)


def _validate_flags(
    *,
    mode: OptimizeMode,
    target_height: int | None,
    fps: float | None,
    crf: int | None,
    encoder: str | None,
    suffix: str,
) -> None:
    if target_height is not None and target_height <= 0:
        raise typer.BadParameter("--target-height must be > 0")
    if fps is not None and fps <= 0:
        raise typer.BadParameter("--fps must be > 0")
    if crf is not None and not (0 <= crf <= 51):
        raise typer.BadParameter("--crf must be in [0, 51]")
    if not suffix:
        raise typer.BadParameter("--suffix must be non-empty")
    if mode == "remux" and (
        target_height is not None or fps is not None or crf is not None or encoder is not None
    ):
        raise typer.BadParameter(
            "Mode remux cannot be combined with --target-height/--fps/--crf/--encoder."
        )


@app.command()
def run(
    input_videos: Annotated[
        list[Path] | None,
        typer.Option("--input", help="One or more input MP4s", exists=True, show_default=False),
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option("--out-dir", dir_okay=True, help="Directory for outputs")
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Optimization mode: auto (default), remux (copy), or transcode (re-encode).",
        ),
    ] = "auto",
    target_height: Annotated[
        int | None,
        typer.Option(
            "--target-height",
            help="Scale to this height in pixels (maintains aspect ratio, implies transcode in auto mode).",
        ),
    ] = None,
    fps: Annotated[
        float | None,
        typer.Option(
            "--fps",
            help="Normalize output framerate (implies transcode in auto mode).",
        ),
    ] = None,
    crf: Annotated[
        int | None,
        typer.Option("--crf", help="Constant rate factor for transcode mode (0-51)."),
    ] = None,
    encoder: Annotated[
        str | None,
        typer.Option("--encoder", help="Force encoder implementation (transcode only)."),
    ] = None,
    faststart: Annotated[
        bool, typer.Option("--faststart/--no-faststart", help="Move moov atom to file head.")
    ] = True,
    suffix: Annotated[
        str, typer.Option("--suffix", help="Suffix appended to output stem.")
    ] = "_optimized",
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing outputs.")] = False,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-input", help="Skip interactive prompts")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Emit planned commands and outputs without execution")
    ] = False,
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
    """Optimize MP4 outputs for web delivery."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    normalized_mode = _normalize_mode(mode)
    _validate_flags(
        mode=normalized_mode,
        target_height=target_height,
        fps=fps,
        crf=crf,
        encoder=encoder,
        suffix=suffix,
    )
    resolved_inputs, resolved_out_dir = _resolve_io(
        input_videos=input_videos,
        out_dir=out_dir,
        prompt_allowed=prompt_allowed,
    )

    try:
        options = OptimizeOptions(
            mode=normalized_mode,
            target_height=target_height,
            fps=fps,
            crf=crf,
            encoder=encoder,
            faststart=faststart,
            suffix=suffix,
            force=force,
            dry_run=dry_run,
        )
        results = optimize(resolved_inputs, resolved_out_dir, options=options)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    run_artifact = resolved_out_dir / "cosmos_optimize_run.v1.json"
    dry_run_plan = resolved_out_dir / "cosmos_optimize_dry_run.json"

    if output_mode == "json":
        payload: dict[str, object] = {
            "command": "cosmos optimize run",
            "mode": normalized_mode,
            "dry_run": dry_run,
            "count": len(results),
            "outputs": [str(p) for p in results],
            "run_artifact": str(run_artifact),
        }
        if dry_run:
            payload["dry_run_plan"] = str(dry_run_plan)
        else:
            payload["artifacts"] = [
                str(p.with_suffix(p.suffix + ".cosmos_optimized.v1.json")) for p in results
            ]
        emit_payload(payload, mode=output_mode)
        return

    if output_mode == "human":
        info(f"Optimize produced {len(results)} file(s)")
        info(f"Run artifact: {run_artifact}")
        if dry_run:
            info(f"Dry-run plan: {dry_run_plan}")
    emit_paths(results, mode=output_mode)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
