from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from cosmos.ffmpeg.detect import resolve_ffprobe_path
from cosmos.video._helpers import _clean_stderr, _coerce_source_path
from cosmos.video.types import VideoProbe, VideoProbeError


def probe_video(path: Path | str) -> VideoProbe:
    """Probe video metadata for the first video stream using ffprobe JSON."""

    source_path = _coerce_source_path(path, error_cls=VideoProbeError)
    ffprobe = resolve_ffprobe_path()
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        (
            "stream=width,height,codec_name,codec_long_name,"
            "avg_frame_rate,r_frame_rate,duration,nb_frames"
            ":format=duration,format_name"
        ),
        "-of",
        "json",
        str(source_path),
    ]
    try:
        completed = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise VideoProbeError(
            f"ffprobe could not be launched at {ffprobe!r}. "
            "Install ffprobe or set COSMOS_FFPROBE to a valid executable."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = _clean_stderr(exc.stderr)
        raise VideoProbeError(
            f"ffprobe failed for {source_path} with exit code {exc.returncode}: {stderr}"
        ) from exc

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoProbeError(f"ffprobe returned invalid JSON for {source_path}: {exc}") from exc

    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise VideoProbeError(f"No video stream found in {source_path}")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise VideoProbeError(f"ffprobe returned an invalid stream payload for {source_path}")

    width = _parse_positive_int(stream.get("width"))
    height = _parse_positive_int(stream.get("height"))
    if width is None or height is None:
        raise VideoProbeError(f"ffprobe did not report usable dimensions for {source_path}")

    fmt = payload.get("format")
    format_payload = fmt if isinstance(fmt, dict) else {}
    duration = _first_float(stream.get("duration"), format_payload.get("duration"))
    fps = _first_rate(stream.get("avg_frame_rate"), stream.get("r_frame_rate"))
    frame_count = _parse_positive_int(stream.get("nb_frames"))

    return VideoProbe(
        source_path=source_path,
        width=width,
        height=height,
        duration_seconds=duration,
        fps=fps,
        frame_count=frame_count,
        codec_name=_optional_str(stream.get("codec_name")),
        codec_long_name=_optional_str(stream.get("codec_long_name")),
        format_name=_optional_str(format_payload.get("format_name")),
    )


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _parse_positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _first_float(*values: object) -> float | None:
    for value in values:
        try:
            parsed = float(str(value))
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed) and parsed > 0:
            return parsed
    return None


def _first_rate(*values: object) -> float | None:
    for value in values:
        parsed = _parse_rate(value)
        if parsed is not None:
            return parsed
    return None


def _parse_rate(value: object) -> float | None:
    if not isinstance(value, str) or not value or value == "0/0":
        return None
    try:
        if "/" in value:
            num_raw, den_raw = value.split("/", 1)
            numerator = float(num_raw)
            denominator = float(den_raw)
            if denominator == 0:
                return None
            rate = numerator / denominator
        else:
            rate = float(value)
    except ValueError:
        return None
    if not math.isfinite(rate) or rate <= 0:
        return None
    return rate


__all__ = ["probe_video"]
