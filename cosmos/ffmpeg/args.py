from __future__ import annotations

from pathlib import Path

from cosmos.ffmpeg.detect import resolve_ffmpeg_path
from cosmos.ffmpeg.presets import build_encoder_settings


def _bitexact_flags() -> list[str]:
    """Return ffmpeg flags that suppress non-deterministic stream metadata."""
    return ["-bitexact", "-fflags", "+bitexact"]


def build_concat_encode_args(
    segments: list[Path],
    output: Path,
    *,
    encoder: str,
    bitexact: bool = False,
) -> list[str]:
    """Return a minimal ffmpeg command for concat and encode.

    This is a placeholder; upstream logic should handle filter_complex, audio, fps, etc.
    """
    # For the placeholder, simply re-encode the first segment
    first = segments[0] if segments else None
    if first is None:
        raise ValueError("No input segments provided")
    args = [
        resolve_ffmpeg_path(),
        "-y",
        "-i",
        str(first),
        "-c:v",
        encoder,
        "-crf",
        "18",
    ]
    if bitexact:
        args += _bitexact_flags()
    args.append(str(output))
    return args


def build_square_crop_args(
    input_path: Path,
    output_path: Path,
    *,
    encoder: str,
    crop_filter: str,
    start: float | None = None,
    end: float | None = None,
    threads: int | None = None,
    bitexact: bool = False,
) -> list[str]:
    args: list[str] = [
        resolve_ffmpeg_path(),
        "-y",
    ]
    if start is not None:
        args += ["-ss", f"{start}"]
    args += ["-i", str(input_path)]
    if end is not None:
        # Use -t (duration) not -to (absolute timestamp) because -ss before -i
        # resets the timestamp origin to 0, making -to equal to duration.
        duration = end - (start or 0)
        args += ["-t", f"{duration}"]
    args += [
        "-vf",
        crop_filter,
        "-c:v",
        encoder,
        "-crf",
        "18",
        "-an",
    ]
    if threads is not None and encoder == "libx264":
        args += ["-threads", str(threads), "-x264-params", f"threads={threads}"]
    if bitexact:
        args += _bitexact_flags()
    args.append(str(output_path))
    return args


def build_optimize_remux_args(
    input_path: Path,
    output_path: Path,
    *,
    faststart: bool,
    bitexact: bool = False,
) -> list[str]:
    args: list[str] = [
        resolve_ffmpeg_path(),
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0",
        "-c",
        "copy",
    ]
    if faststart:
        args += ["-movflags", "faststart"]
    if bitexact:
        args += _bitexact_flags()
    args += [str(output_path)]
    return args


def build_optimize_transcode_args(
    input_path: Path,
    output_path: Path,
    *,
    encoder: str,
    target_height: int | None,
    fps: float | None,
    crf: int | None,
    faststart: bool,
    threads: int | None = None,
    bitexact: bool = False,
) -> list[str]:
    args: list[str] = [
        resolve_ffmpeg_path(),
        "-y",
        "-i",
        str(input_path),
    ]

    filters: list[str] = []
    if target_height is not None:
        filters.append(f"scale=-2:{target_height}:flags=lanczos")
    if fps is not None:
        filters.append(f"fps={fps:g}")
    if filters:
        args += ["-vf", ",".join(filters)]

    args += build_encoder_settings(encoder, mode="balanced", crf=crf, threads=threads)
    args += ["-c:a", "copy"]
    if faststart:
        args += ["-movflags", "faststart"]
    if bitexact:
        args += _bitexact_flags()
    args += [str(output_path)]
    return args
