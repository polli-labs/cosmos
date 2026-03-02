from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, replace
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
logger = logging.getLogger(__name__)


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
    profile: str | None = None  # determinism profile name; None = legacy behaviour


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


def _build_transcode_command(
    src: Path,
    out_path: Path,
    *,
    options: OptimizeOptions,
    encoder: str,
    threads: int | None = None,
    bitexact: bool = False,
) -> list[str]:
    return build_optimize_transcode_args(
        src,
        out_path,
        encoder=encoder,
        target_height=options.target_height,
        fps=options.fps,
        crf=options.crf,
        faststart=options.faststart,
        threads=threads,
        bitexact=bitexact,
    )


def _plan_input(
    src: Path,
    out_dir: Path,
    *,
    mode: OptimizeMode,
    options: OptimizeOptions,
    threads: int | None = None,
    bitexact: bool = False,
) -> tuple[
    Path,
    Literal["remux", "transcode"],
    list[str],
    dict[str, object] | None,
    str | None,
]:
    resolved_mode = _resolve_mode_for_input(mode, options)
    out_path = _output_for(src, out_dir, options.suffix)
    if out_path.exists() and not options.force:
        raise FileExistsError(
            f"Output already exists: {out_path} (use --force to overwrite existing files)"
        )

    if resolved_mode == "remux":
        cmd = build_optimize_remux_args(
            src, out_path, faststart=options.faststart, bitexact=bitexact
        )
        return out_path, resolved_mode, cmd, {"impl": "copy", "codec": "copy"}, None

    if options.encoder is not None:
        selected_encoder = options.encoder
        attempted_encoder = options.encoder
    else:
        selected_encoder, attempted_encoder = choose_encoder_for_video(src)
    cmd = _build_transcode_command(
        src,
        out_path,
        options=options,
        encoder=selected_encoder,
        threads=threads,
        bitexact=bitexact,
    )
    encode_info: dict[str, object] = {
        "impl": selected_encoder,
        "codec": selected_encoder,
        "crf": options.crf,
    }
    if attempted_encoder != selected_encoder:
        encode_info["hardware_attempted"] = attempted_encoder
    return out_path, resolved_mode, cmd, encode_info, attempted_encoder


def _run_with_optional_fallback(
    *,
    src: Path,
    out_path: Path,
    options: OptimizeOptions,
    resolved_mode: Literal["remux", "transcode"],
    cmd: list[str],
    encode_info: dict[str, object] | None,
    attempted_encoder: str | None,
    threads: int | None = None,
    bitexact: bool = False,
) -> dict[str, object] | None:
    try:
        subprocess.run(cmd, check=True)  # noqa: S603
        return encode_info
    except subprocess.CalledProcessError as exc:
        # Preserve explicit user-selected encoder behavior; only auto-selection
        # gets an automatic fallback to software x264.
        if (
            resolved_mode != "transcode"
            or options.encoder is not None
            or attempted_encoder in {None, "libx264"}
        ):
            raise
        logger.warning(
            "hardware encoder %s failed (%s); retrying with libx264", attempted_encoder, exc
        )
        fallback_cmd = _build_transcode_command(
            src,
            out_path,
            options=options,
            encoder="libx264",
            threads=threads,
            bitexact=bitexact,
        )
        subprocess.run(fallback_cmd, check=True)  # noqa: S603
        return {
            "impl": "libx264",
            "codec": "libx264",
            "crf": options.crf,
            "hardware_attempted": attempted_encoder,
        }


def optimize(
    input_videos: list[Path],
    out_dir: Path,
    *,
    options: OptimizeOptions,
) -> list[Path]:
    from cosmos.sdk.profiles import DeterminismProfile, resolve_profile

    mode = _validate_options(options)
    if not input_videos:
        raise ValueError("At least one input video is required")

    for src in input_videos:
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Input video not found: {src}")

    ensure_dir(out_dir)
    ensure_ffmpeg_available()

    # -- resolve determinism profile ------------------------------------------
    profile: DeterminismProfile | None = resolve_profile(options.profile)
    if profile is not None:
        # Apply profile defaults where no explicit option was set
        if options.encoder is None and profile.pinned_encoder is not None:
            options = replace(options, encoder=profile.pinned_encoder)
    profile_threads = profile.threads if profile else None
    profile_bitexact = profile.bitexact if profile else False

    run_options: dict[str, object] = {
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
    if profile is not None:
        run_options["profile"] = profile.to_dict()
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
        out_path, resolved_mode, cmd, encode_info, attempted_encoder = _plan_input(
            src,
            out_dir,
            mode=mode,
            options=options,
            threads=profile_threads,
            bitexact=profile_bitexact,
        )

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
            encode_info = _run_with_optional_fallback(
                src=src,
                out_path=out_path,
                options=options,
                resolved_mode=resolved_mode,
                cmd=cmd,
                encode_info=encode_info,
                attempted_encoder=attempted_encoder,
                threads=profile_threads,
                bitexact=profile_bitexact,
            )
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
