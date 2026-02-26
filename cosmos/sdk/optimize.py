from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from cosmos.ffmpeg.args import build_optimize_remux_args, build_optimize_transcode_args
from cosmos.ffmpeg.detect import choose_encoder_for_video, ensure_ffmpeg_available
from cosmos.sdk.provenance import (
    emit_optimize_run,
    emit_optimized_artifact,
    ffprobe_video,
    sha256_file,
)
from cosmos.utils.io import ensure_dir

OptimizeMode = Literal["auto", "remux", "transcode"]


@dataclass
class OptimizeOptions:
    mode: OptimizeMode = "auto"
    target_height: int | None = None
    fps: float | None = None
    crf: int | None = None
    encoder: str | None = None
    faststart: bool = True
    suffix: str = "_optimized"
    force: bool = False
    dry_run: bool = False
    skip_ffmpeg_check: bool = False


def _normalize_mode(mode: str) -> OptimizeMode:
    normalized = mode.strip().lower()
    if normalized not in {"auto", "remux", "transcode"}:
        raise ValueError(f"mode must be one of auto|remux|transcode (got {mode!r})")
    return cast(OptimizeMode, normalized)


def _validate_options(options: OptimizeOptions) -> OptimizeMode:
    mode = _normalize_mode(options.mode)

    if options.target_height is not None and options.target_height <= 0:
        raise ValueError("target_height must be > 0")
    if options.fps is not None and options.fps <= 0:
        raise ValueError("fps must be > 0")
    if options.crf is not None and not (0 <= options.crf <= 51):
        raise ValueError("crf must be in [0, 51]")
    if not options.suffix:
        raise ValueError("suffix must be non-empty")

    if mode == "remux" and (
        options.target_height is not None
        or options.fps is not None
        or options.crf is not None
        or options.encoder is not None
    ):
        raise ValueError("remux mode does not allow target_height/fps/crf/encoder options")

    return mode


def _resolve_mode_for_input(
    mode: OptimizeMode, options: OptimizeOptions
) -> Literal["remux", "transcode"]:
    if mode == "remux":
        return "remux"
    if mode == "transcode":
        return "transcode"
    # auto
    if (
        options.target_height is not None
        or options.fps is not None
        or options.crf is not None
        or options.encoder is not None
    ):
        return "transcode"
    return "remux"


def _output_for(source: Path, out_dir: Path, suffix: str) -> Path:
    stem = source.stem
    return out_dir / f"{stem}{suffix}.mp4"


def optimize(
    input_videos: list[Path],
    out_dir: Path,
    *,
    options: OptimizeOptions,
) -> list[Path]:
    mode = _validate_options(options)
    if not input_videos:
        raise ValueError("At least one input video is required")

    for src in input_videos:
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Input video not found: {src}")

    ensure_dir(out_dir)
    if not options.skip_ffmpeg_check:
        ensure_ffmpeg_available()

    run_options = {
        "mode": mode,
        "target_height": options.target_height,
        "fps": options.fps,
        "crf": options.crf,
        "encoder": options.encoder,
        "faststart": options.faststart,
        "suffix": options.suffix,
        "force": options.force,
        "dry_run": options.dry_run,
    }
    input_summary = [
        {
            "path": str(src),
            "sha256": sha256_file(src),
            "video": ffprobe_video(src),
        }
        for src in input_videos
    ]
    optimize_run_id, _run_path = emit_optimize_run(
        output_dir=out_dir,
        options=run_options,
        inputs=input_summary,
    )

    outputs: list[Path] = []
    plan_entries: list[dict[str, object]] = []
    for src in input_videos:
        resolved_mode = _resolve_mode_for_input(mode, options)
        out_path = _output_for(src, out_dir, options.suffix)
        if out_path.exists() and not options.force:
            raise FileExistsError(
                f"Output already exists: {out_path} (use --force to overwrite existing files)"
            )

        if resolved_mode == "remux":
            cmd = build_optimize_remux_args(
                src,
                out_path,
                faststart=options.faststart,
            )
            encode_info: dict[str, object] | None = {"impl": "copy", "codec": "copy"}
        else:
            resolved_encoder = options.encoder or choose_encoder_for_video(src)[0]
            cmd = build_optimize_transcode_args(
                src,
                out_path,
                encoder=resolved_encoder,
                target_height=options.target_height,
                fps=options.fps,
                crf=options.crf,
                faststart=options.faststart,
            )
            encode_info = {
                "impl": resolved_encoder,
                "codec": resolved_encoder,
                "crf": options.crf,
            }

        transform: dict[str, object] = {
            "mode": resolved_mode,
            "faststart": options.faststart,
            "target_height": options.target_height,
            "fps": options.fps,
            "crf": options.crf,
        }
        clean_transform = {k: v for k, v in transform.items() if v is not None}

        if options.dry_run:
            plan_entries.append(
                {
                    "input": str(src),
                    "output": str(out_path),
                    "mode": resolved_mode,
                    "command": cmd,
                }
            )
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(cmd, check=True)  # noqa: S603
            emit_optimized_artifact(
                optimize_run_id=optimize_run_id,
                mode=resolved_mode,
                source_path=src,
                output_path=out_path,
                transform=clean_transform,
                encode_info=encode_info,
            )

        outputs.append(out_path)

    if options.dry_run:
        plan_path = out_dir / "cosmos_optimize_dry_run.json"
        plan_path.write_text(json.dumps({"planned": plan_entries}, indent=2))

    return outputs
