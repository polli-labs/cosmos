from __future__ import annotations

from enum import Enum
from typing import Literal

Quality = Literal["quality", "balanced", "performance", "low_memory", "minimal"]


class Encoder(str, Enum):
    VTB = "h264_videotoolbox"
    NVENC = "h264_nvenc"
    QSV = "h264_qsv"
    AMF = "h264_amf"
    X264 = "libx264"


def default_crf(mode: Quality) -> int:
    return {
        "quality": 18,
        "balanced": 23,
        "performance": 28,
        "low_memory": 23,
        "minimal": 28,
    }[mode]


def build_encoder_settings(encoder: str, *, mode: str, crf: int | None = None, threads: int | None = None) -> list[str]:
    """Return ffmpeg args for encoder settings based on mode and crf/thread overrides."""
    # Normalize mode
    m = str(mode).lower()
    crf_val = crf if crf is not None else default_crf(m)  # type: ignore[arg-type]
    if encoder == Encoder.NVENC.value:
        preset = "p7" if mode == "quality" else "p4"
        return ["-c:v", Encoder.NVENC.value, "-preset", preset, "-qp", str(crf_val)]
    if encoder == Encoder.VTB.value:
        return [
            "-c:v",
            Encoder.VTB.value,
            "-allow_sw",
            "1",
            "-realtime",
            "0",
            "-b:v",
            "0",
            "-crf",
            str(crf_val),
        ]
    if encoder == Encoder.QSV.value:
        # Prefer QSV when present; use ICQ-like mapping via global_quality and disable bitrate for CRF-like behavior
        return ["-c:v", Encoder.QSV.value, "-global_quality", str(crf_val), "-b:v", "0"]
    if encoder == Encoder.AMF.value:
        # AMF: use constant QP mode for reproducibility
        return [
            "-c:v",
            Encoder.AMF.value,
            "-rc",
            "cqp",
            "-quality",
            "quality",
            "-qp_i",
            str(crf_val),
            "-qp_p",
            str(crf_val),
        ]
    # libx264 default
    args = ["-c:v", Encoder.X264.value, "-preset", ("slower" if mode == "quality" else "medium"), "-crf", str(crf_val)]
    if threads is not None:
        args += ["-threads", str(threads), "-x264-params", f"threads={threads}"]
    return args
