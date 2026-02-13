from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import questionary
import typer

from cosmos.sdk.crop import CropJob, RectCropJob, crop

app = typer.Typer(help="Post-processing crop (square or rectangular)")


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
    skip_ffmpeg_check: Annotated[
        bool,
        typer.Option(
            "--skip-ffmpeg-check",
            help="Skip the NVENC ffmpeg bootstrap check (for CI/headless use).",
        ),
    ] = False,
) -> None:
    """Run crop in interactive or agent (non-interactive) mode."""
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and not non_interactive)
    crop_mode = crop_mode.strip().lower()
    if crop_mode not in {"square", "rect"}:
        raise typer.BadParameter("crop_mode must be one of: square, rect")
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

        parsed_jobs = parse_jobs_json(jobs_file)
    elif crop_mode == "rect":
        if any(v is None for v in (x0, y0, width, height)):
            raise typer.BadParameter(
                "--crop-mode rect requires --x0 --y0 --width --height when --jobs-file is not set"
            )
        rect_x0 = cast(float, x0)
        rect_y0 = cast(float, y0)
        rect_w = cast(float, width)
        rect_h = cast(float, height)
        parsed_jobs = [
            RectCropJob(
                x0=rect_x0,
                y0=rect_y0,
                w=rect_w,
                h=rect_h,
                normalized=not px,
                start=trim_start,
                end=trim_end,
            )
        ]
    else:
        if any(v is not None for v in (x0, y0, width, height)) or px:
            raise typer.BadParameter("Rect options require --crop-mode rect")
        parsed_jobs = [
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
    results = crop(
        videos,
        parsed_jobs,
        out_dir,
        ffmpeg_opts={"dry_run": dry_run, "prefer_hevc_hw": prefer_hevc_hw},
    )
    for p in results:
        typer.echo(str(p))


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
        bool, typer.Option("--yes", help="Skip confirmation prompt")
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
) -> None:
    """Crop views from a curated-views-spec JSON."""
    from cosmos.crop.curated_views import parse_curated_views
    from cosmos.ffmpeg.detect import prompt_bootstrap_if_needed

    prompt_bootstrap_if_needed(interactive=not skip_ffmpeg_check and not non_interactive)

    pairs = parse_curated_views(spec, source_root, clip_pattern=clip_pattern)

    # Summary table
    typer.echo(f"\n{'View ID':<40} {'Source':<30} {'Crop (norm)':<30}")
    typer.echo("-" * 100)
    for src, job in pairs:
        crop_str = f"x0={job.x0:.3f} y0={job.y0:.3f} w={job.w:.3f} h={job.h:.3f}"
        typer.echo(f"{job.view_id or '?':<40} {src.name:<30} {crop_str:<30}")
    typer.echo(f"\nTotal: {len(pairs)} views")

    if not non_interactive and not dry_run:
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

    action = "Would produce" if dry_run else "Produced"
    typer.echo(f"\n{action} {len(results)} cropped views in {out_dir}")
    for p in results:
        typer.echo(f"  {p}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
