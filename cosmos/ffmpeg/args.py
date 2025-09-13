from __future__ import annotations

from pathlib import Path


def build_concat_encode_args(segments: list[Path], output: Path, *, encoder: str) -> list[str]:
    """Return a minimal ffmpeg command for concat and encode.

    This is a placeholder; upstream logic should handle filter_complex, audio, fps, etc.
    """
    # For the placeholder, simply re-encode the first segment
    first = segments[0] if segments else None
    if first is None:
        raise ValueError("No input segments provided")
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(first),
        "-c:v",
        encoder,
        "-crf",
        "18",
        str(output),
    ]


def build_square_crop_args(
    input_path: Path,
    output_path: Path,
    *,
    encoder: str,
    crop_filter: str,
    start: float | None = None,
    end: float | None = None,
) -> list[str]:
    args: list[str] = [
        "ffmpeg",
        "-y",
    ]
    if start is not None:
        args += ["-ss", f"{start}"]
    args += ["-i", str(input_path)]
    if end is not None:
        args += ["-to", f"{end}"]
    args += [
        "-vf",
        crop_filter,
        "-c:v",
        encoder,
        "-crf",
        "18",
        "-an",
        str(output_path),
    ]
    return args
