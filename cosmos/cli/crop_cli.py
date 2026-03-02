from __future__ import annotations

from pathlib import Path
from typing import Annotated

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
from cosmos.sdk.crop import CropJob, RectCropJob, crop
from cosmos.sdk.preview import RenderOptions
from cosmos.sdk.preview import preview as sdk_preview
from cosmos.sdk.preview import preview_curated_views as sdk_preview_curated_views

app = typer.Typer(help="Post-processing crop (square or rectangular)")
CropJobs = list[CropJob] | list[RectCropJob]

PreviewFrameOption = Annotated[
    list[str] | None,
    typer.Option(
        "--frame",
        help="Frame selector(s): start|mid|end, start+2.0/end-1.0, or absolute seconds.",
    ),
]
PreviewStackTimeOption = Annotated[
    list[float] | None,
    typer.Option(
        "--stack-time",
        help="Absolute seconds for stacked overlays (repeatable). Defaults to 0.",
    ),
]
PreviewRenderMaxWidthOption = Annotated[
    int,
    typer.Option("--render-max-width", help="Maximum width (px) for extracted preview frames."),
]
PreviewGridStepOption = Annotated[
    int,
    typer.Option("--grid-step-px", help="Grid/ruler step in pixels. Set 0 to disable."),
]
PreviewShowRulersOption = Annotated[
    bool,
    typer.Option("--show-rulers/--no-rulers", help="Render ruler ticks/labels on overlays."),
]
PreviewShowCrosshairOption = Annotated[
    bool,
    typer.Option("--show-crosshair/--no-crosshair", help="Render a center crosshair per crop."),
]
PreviewAlphaOption = Annotated[
    float,
    typer.Option("--alpha", help="Overlay fill alpha in [0,1] for per-view contact cells."),
]
PreviewSourceShaOption = Annotated[
    bool,
    typer.Option(
        "--source-sha/--no-source-sha",
        help="Hash source videos into preview plan metadata (slower on large files).",
    ),
]


def _resolve_crop_mode(raw_mode: str) -> str:
    mode = raw_mode.strip().lower()
    if mode not in {"square", "rect"}:
        raise typer.BadParameter("crop_mode must be one of: square, rect")
    return mode


def _resolve_io_paths(
    *,
    input_videos: list[Path] | None,
    out_dir: Path | None,
    prompt_allowed: bool,
) -> tuple[list[Path], Path]:
    videos: list[Path] = input_videos or []
    if prompt_allowed and not videos:
        sel = questionary.text("Enter comma-separated MP4 paths:").ask() or ""
        videos = [Path(s.strip()) for s in sel.split(",") if s.strip()]
    if prompt_allowed and out_dir is None:
        selected = questionary.path("Select output directory:").ask() or "."
        out_dir = Path(selected)
    if out_dir is None:
        raise typer.BadParameter(
            "Output directory is required (set --yes/--no-input for non-interactive runs)."
        )
    return videos, out_dir


def _jobs_from_rect_flags(
    *,
    x0: float | None,
    y0: float | None,
    width: float | None,
    height: float | None,
    px: bool,
    trim_start: float | None,
    trim_end: float | None,
) -> list[RectCropJob]:
    if x0 is None or y0 is None or width is None or height is None:
        raise typer.BadParameter(
            "--crop-mode rect requires --x0 --y0 --width --height when --jobs-file is not set"
        )
    return [
        RectCropJob(
            x0=x0,
            y0=y0,
            w=width,
            h=height,
            normalized=not px,
            start=trim_start,
            end=trim_end,
        )
    ]


def _jobs_from_square_flags(
    *,
    size: int,
    offset_x: float | None,
    offset_y: float | None,
    center_x: float | None,
    center_y: float | None,
    x0: float | None,
    y0: float | None,
    width: float | None,
    height: float | None,
    px: bool,
    trim_start: float | None,
    trim_end: float | None,
) -> list[CropJob]:
    if any(value is not None for value in (x0, y0, width, height)) or px:
        raise typer.BadParameter("Rect options require --crop-mode rect")
    return [
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


def _resolve_jobs(
    *,
    jobs_file: Path | None,
    crop_mode: str,
    size: int,
    offset_x: float | None,
    offset_y: float | None,
    center_x: float | None,
    center_y: float | None,
    x0: float | None,
    y0: float | None,
    width: float | None,
    height: float | None,
    px: bool,
    trim_start: float | None,
    trim_end: float | None,
) -> CropJobs:
    if jobs_file:
        from cosmos.crop.jobs import parse_jobs_json

        return parse_jobs_json(jobs_file)
    if crop_mode == "rect":
        return _jobs_from_rect_flags(
            x0=x0,
            y0=y0,
            width=width,
            height=height,
            px=px,
            trim_start=trim_start,
            trim_end=trim_end,
        )
    return _jobs_from_square_flags(
        size=size,
        offset_x=offset_x,
        offset_y=offset_y,
        center_x=center_x,
        center_y=center_y,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        px=px,
        trim_start=trim_start,
        trim_end=trim_end,
    )


def _resolve_preview_options(
    *,
    frame_selectors: list[str] | None,
    stack_times: list[float] | None,
    render_max_width: int,
    grid_step_px: int,
    show_rulers: bool,
    show_crosshair: bool,
    alpha: float,
    dry_run: bool,
    include_source_sha: bool,
) -> RenderOptions:
    selectors = frame_selectors or ["start"]
    stacks = stack_times or [0.0]
    if render_max_width <= 0:
        raise typer.BadParameter("--render-max-width must be > 0")
    if grid_step_px < 0:
        raise typer.BadParameter("--grid-step-px must be >= 0")
    if alpha < 0.0 or alpha > 1.0:
        raise typer.BadParameter("--alpha must be in [0,1]")
    return RenderOptions(
        frame_selectors=selectors,
        stack_times_sec=stacks,
        render_max_width=render_max_width,
        grid_step_px=grid_step_px,
        show_rulers=show_rulers,
        show_crosshair=show_crosshair,
        alpha=alpha,
        dry_run=dry_run,
        include_source_sha=include_source_sha,
    )


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
        bool,
        typer.Option(
            "--yes",
            "--no-input",
            "--no-tui",
            help="Skip interactive prompts (agent mode)",
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Build commands; do not execute")
    ] = False,
    jobs_file: Annotated[
        Path | None,
        typer.Option("--jobs-file", exists=True, help="Crop jobs JSON (offsets/targets/trims)"),
    ] = None,
    crop_mode: Annotated[
        str, typer.Option("--crop-mode", help="Crop mode: square (default) or rect")
    ] = "square",
    # Square mode params
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
    # Rect mode params
    x0: Annotated[
        float | None,
        typer.Option("--x0", help="Rect crop: left edge (normalized 0-1 or pixels with --px)"),
    ] = None,
    y0: Annotated[
        float | None,
        typer.Option("--y0", help="Rect crop: top edge (normalized 0-1 or pixels with --px)"),
    ] = None,
    width: Annotated[
        float | None,
        typer.Option("--width", help="Rect crop: width (normalized 0-1 or pixels with --px)"),
    ] = None,
    height: Annotated[
        float | None,
        typer.Option("--height", help="Rect crop: height (normalized 0-1 or pixels with --px)"),
    ] = None,
    px: Annotated[
        bool,
        typer.Option("--px", help="Interpret rect coords as pixels instead of normalized 0-1"),
    ] = False,
    # Shared params
    trim_start: Annotated[
        float | None,
        typer.Option(help="Optional trim start in seconds (time-based)."),
    ] = None,
    trim_end: Annotated[
        float | None,
        typer.Option(help="Optional trim end in seconds (time-based)."),
    ] = None,
    prefer_hevc_hw: Annotated[
        bool,
        typer.Option(
            "--prefer-hevc-hw",
            help="On macOS, try hevc_videotoolbox before H.264 hardware when available (useful for >4K inputs).",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="Determinism profile (strict|balanced|throughput). "
            "Controls encoder, threads, and bitexact flags for reproducibility.",
        ),
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
    """Run crop in interactive or agent (non-interactive) mode."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)
    normalized_mode = _resolve_crop_mode(crop_mode)
    videos, resolved_out_dir = _resolve_io_paths(
        input_videos=input_videos,
        out_dir=out_dir,
        prompt_allowed=prompt_allowed,
    )

    # Default jobs or parse from file
    try:
        parsed_jobs = _resolve_jobs(
            jobs_file=jobs_file,
            crop_mode=normalized_mode,
            size=size,
            offset_x=offset_x,
            offset_y=offset_y,
            center_x=center_x,
            center_y=center_y,
            x0=x0,
            y0=y0,
            width=width,
            height=height,
            px=px,
            trim_start=trim_start,
            trim_end=trim_end,
        )
        results = crop(
            videos,
            parsed_jobs,
            resolved_out_dir,
            ffmpeg_opts={
                "dry_run": dry_run,
                "prefer_hevc_hw": prefer_hevc_hw,
                "profile": profile,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos crop run",
                "mode": normalized_mode,
                "dry_run": dry_run,
                "count": len(results),
                "outputs": [str(p) for p in results],
            },
            mode=output_mode,
        )
        return

    emit_paths(results, mode=output_mode)


@app.command(name="preview")
def preview(
    input_videos: Annotated[
        list[Path] | None,
        typer.Option("--input", help="One or more input MP4s", exists=True, show_default=False),
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option("--out", dir_okay=True, help="Directory for preview outputs")
    ] = None,
    jobs_file: Annotated[
        Path | None,
        typer.Option("--jobs-file", exists=True, help="Crop jobs JSON (square or rect)"),
    ] = None,
    crop_mode: Annotated[
        str,
        typer.Option("--crop-mode", help="Crop mode for flag-based jobs: square (default) or rect"),
    ] = "square",
    size: Annotated[
        int, typer.Option(help="Square target size (pixels) when not using --jobs-file")
    ] = 1080,
    offset_x: Annotated[
        float | None,
        typer.Option(
            help="Margin-relative horizontal offset [-1,1]. Cannot be combined with centers."
        ),
    ] = None,
    offset_y: Annotated[
        float | None,
        typer.Option(
            help="Margin-relative vertical offset [-1,1]. Cannot be combined with centers."
        ),
    ] = None,
    center_x: Annotated[
        float | None,
        typer.Option(help="Absolute center X in [0,1] for square mode when offsets are omitted."),
    ] = None,
    center_y: Annotated[
        float | None,
        typer.Option(help="Absolute center Y in [0,1] for square mode when offsets are omitted."),
    ] = None,
    x0: Annotated[
        float | None,
        typer.Option("--x0", help="Rect crop: left edge (normalized 0-1 or pixels with --px)"),
    ] = None,
    y0: Annotated[
        float | None,
        typer.Option("--y0", help="Rect crop: top edge (normalized 0-1 or pixels with --px)"),
    ] = None,
    width: Annotated[
        float | None,
        typer.Option("--width", help="Rect crop: width (normalized 0-1 or pixels with --px)"),
    ] = None,
    height: Annotated[
        float | None,
        typer.Option("--height", help="Rect crop: height (normalized 0-1 or pixels with --px)"),
    ] = None,
    px: Annotated[
        bool,
        typer.Option("--px", help="Interpret rect coords as pixels instead of normalized 0-1"),
    ] = False,
    trim_start: Annotated[
        float | None,
        typer.Option(help="Optional trim start in seconds (for flag-based single-job mode)."),
    ] = None,
    trim_end: Annotated[
        float | None,
        typer.Option(help="Optional trim end in seconds (for flag-based single-job mode)."),
    ] = None,
    frame: PreviewFrameOption = None,
    stack_time: PreviewStackTimeOption = None,
    render_max_width: PreviewRenderMaxWidthOption = 1600,
    grid_step_px: PreviewGridStepOption = 400,
    show_rulers: PreviewShowRulersOption = True,
    show_crosshair: PreviewShowCrosshairOption = True,
    alpha: PreviewAlphaOption = 0.25,
    include_source_sha: PreviewSourceShaOption = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--yes", "--no-input", "--no-tui", help="Skip interactive prompts (agent mode)"
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Build preview plan and artifact paths; do not render images"
        ),
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
    """Render non-interactive crop preview contact sheets + stacked overlays."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    try:
        normalized_mode = _resolve_crop_mode(crop_mode)
        videos, resolved_out_dir = _resolve_io_paths(
            input_videos=input_videos,
            out_dir=out_dir,
            prompt_allowed=prompt_allowed,
        )
        parsed_jobs = _resolve_jobs(
            jobs_file=jobs_file,
            crop_mode=normalized_mode,
            size=size,
            offset_x=offset_x,
            offset_y=offset_y,
            center_x=center_x,
            center_y=center_y,
            x0=x0,
            y0=y0,
            width=width,
            height=height,
            px=px,
            trim_start=trim_start,
            trim_end=trim_end,
        )
        options = _resolve_preview_options(
            frame_selectors=frame,
            stack_times=stack_time,
            render_max_width=render_max_width,
            grid_step_px=grid_step_px,
            show_rulers=show_rulers,
            show_crosshair=show_crosshair,
            alpha=alpha,
            dry_run=dry_run,
            include_source_sha=include_source_sha,
        )
        result = sdk_preview(videos, parsed_jobs, resolved_out_dir, options=options)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    outputs = result.outputs
    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos crop preview",
                "dry_run": dry_run,
                "run_artifact": str(result.run_path),
                "clip_plans": [str(path) for path in result.clip_plan_paths],
                "sheets": [str(path) for path in result.sheet_paths],
                "stacked": [str(path) for path in result.stacked_paths],
                "outputs": [str(path) for path in outputs],
                "count": len(outputs),
            },
            mode=output_mode,
        )
        return

    emit_paths(outputs, mode=output_mode)


@app.command(name="curated-views-preview")
def curated_views_preview(
    spec: Annotated[Path, typer.Option("--spec", exists=True, help="Curated views spec JSON")],
    source_root: Annotated[
        Path, typer.Option("--source-root", exists=True, help="Root directory of source clips")
    ],
    out_dir: Annotated[Path, typer.Option("--out", help="Output directory for preview bundles")],
    clip_pattern: Annotated[
        str,
        typer.Option(
            "--clip-pattern", help="Pattern for source clips (default: {date}/8k/{clip}.mp4)"
        ),
    ] = "{date}/8k/{clip}.mp4",
    frame: PreviewFrameOption = None,
    stack_time: PreviewStackTimeOption = None,
    render_max_width: PreviewRenderMaxWidthOption = 1600,
    grid_step_px: PreviewGridStepOption = 400,
    show_rulers: PreviewShowRulersOption = True,
    show_crosshair: PreviewShowCrosshairOption = True,
    alpha: PreviewAlphaOption = 0.25,
    include_source_sha: PreviewSourceShaOption = False,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-input", help="Skip confirmation prompt")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Build preview plan and artifact paths; do not render images"
        ),
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
    """Render non-interactive crop preview artifacts for curated views specs."""
    from cosmos.crop.curated_views import parse_curated_views
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    try:
        pairs = parse_curated_views(spec, source_root, clip_pattern=clip_pattern)
        if output_mode == "human":
            info(f"{len(pairs)} curated views parsed from spec")
        options = _resolve_preview_options(
            frame_selectors=frame,
            stack_times=stack_time,
            render_max_width=render_max_width,
            grid_step_px=grid_step_px,
            show_rulers=show_rulers,
            show_crosshair=show_crosshair,
            alpha=alpha,
            dry_run=dry_run,
            include_source_sha=include_source_sha,
        )
        result = sdk_preview_curated_views(pairs, out_dir, options=options)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    outputs = result.outputs
    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos crop curated-views-preview",
                "dry_run": dry_run,
                "run_artifact": str(result.run_path),
                "clip_plans": [str(path) for path in result.clip_plan_paths],
                "sheets": [str(path) for path in result.sheet_paths],
                "stacked": [str(path) for path in result.stacked_paths],
                "outputs": [str(path) for path in outputs],
                "count": len(outputs),
            },
            mode=output_mode,
        )
        return

    emit_paths(outputs, mode=output_mode)


@app.command(name="curated-views")
def curated_views(
    spec: Annotated[Path, typer.Option("--spec", exists=True, help="Curated views spec JSON")],
    source_root: Annotated[
        Path, typer.Option("--source-root", exists=True, help="Root directory of source clips")
    ],
    out_dir: Annotated[Path, typer.Option("--out", help="Output directory for cropped views")],
    clip_pattern: Annotated[
        str,
        typer.Option(
            "--clip-pattern", help="Pattern for source clips (default: {date}/8k/{clip}.mp4)"
        ),
    ] = "{date}/8k/{clip}.mp4",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Build commands; do not execute")
    ] = False,
    non_interactive: Annotated[
        bool, typer.Option("--yes", "--no-input", help="Skip confirmation prompt")
    ] = False,
    prefer_hevc_hw: Annotated[
        bool,
        typer.Option("--prefer-hevc-hw", help="Try HEVC hardware encoder"),
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
    """Crop views from a curated-views-spec JSON."""
    from cosmos.crop.curated_views import parse_curated_views
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    output_mode = resolve_output_mode(json_out=json_out, plain_out=plain_out)
    prompt_allowed = can_prompt(no_input=non_interactive)
    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and prompt_allowed)

    try:
        pairs = parse_curated_views(spec, source_root, clip_pattern=clip_pattern)

        if output_mode == "human":
            info(f"{len(pairs)} curated views parsed from spec")
            for src, job in pairs:
                crop_str = f"x0={job.x0:.3f} y0={job.y0:.3f} w={job.w:.3f} h={job.h:.3f}"
                info(f"{job.view_id or '?'} :: {src.name} :: {crop_str}")

        if prompt_allowed and not dry_run:
            if not questionary.confirm("Proceed with crop?", default=True).ask():
                raise typer.Abort()

        # Group by source and crop each view
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for src, job in pairs:
            out_paths = crop(
                [src],
                [job],
                out_dir,
                ffmpeg_opts={"dry_run": dry_run, "prefer_hevc_hw": prefer_hevc_hw},
            )
            results.extend(out_paths)
    except Exception as exc:  # noqa: BLE001
        raise_mapped_exit(exc)
        return

    if output_mode == "json":
        emit_payload(
            {
                "command": "cosmos crop curated-views",
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
