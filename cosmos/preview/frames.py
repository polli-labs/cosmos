from __future__ import annotations

import subprocess
from pathlib import Path

from cosmos.ffmpeg.detect import ensure_ffmpeg_available, resolve_ffmpeg_path


def time_tag(time_sec: float) -> str:
    return f"t_{time_sec:07.3f}"


def frame_name_for_time(time_sec: float) -> str:
    return f"{time_tag(time_sec)}.png"


def _scale_filter(max_width: int) -> str:
    if max_width <= 0:
        return "scale=iw:ih"
    return f"scale=min(iw\\,{max_width}):-2"


def build_extract_frame_args(
    *,
    input_video: Path,
    time_sec: float,
    output_path: Path,
    max_width: int,
) -> list[str]:
    vf = _scale_filter(max_width)
    return [
        resolve_ffmpeg_path(),
        "-y",
        "-ss",
        f"{time_sec:.3f}",
        "-i",
        str(input_video),
        "-frames:v",
        "1",
        "-vf",
        vf,
        str(output_path),
    ]


def extract_frame(
    *,
    input_video: Path,
    time_sec: float,
    output_path: Path,
    max_width: int,
    dry_run: bool,
) -> list[str]:
    args = build_extract_frame_args(
        input_video=input_video,
        time_sec=time_sec,
        output_path=output_path,
        max_width=max_width,
    )
    if dry_run:
        return args

    ensure_ffmpeg_available()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
    return args
