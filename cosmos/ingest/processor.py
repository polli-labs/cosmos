from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING  # noqa: F401  # (kept for potential future typing guards)

# ruff: noqa: UP035,S603,S607
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cosmos.ffmpeg.presets import build_encoder_settings

from .manifest import ClipInfo
from .validation import ClipValidationResult, SegmentInfo

# Ensure a Windows-specific constant exists for tests on non-Windows platforms
# Provide a shim for tests on non-Windows platforms
if not hasattr(subprocess, "CREATE_NO_WINDOW"):
    # Assigning is safe here and used only in tests on non-Windows
    subprocess.CREATE_NO_WINDOW = 0  # type: ignore[attr-defined]
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ProcessingMode(Enum):
    QUALITY = "quality"        # Highest quality, all threads
    BALANCED = "balanced"      # Good quality, all threads
    PERFORMANCE = "performance"      # Faster, all threads
    LOW_MEMORY = "low_memory"  # Half threads
    MINIMAL = "minimal"        # Single thread


@dataclass
class ProcessingOptions:
    """Configuration for video processing"""
    output_resolution: tuple[int, int]  # Width, height
    quality_mode: ProcessingMode
    low_memory: bool = False
    crf: int | None = None  # Custom CRF value if specified


class EncoderType(Enum):
    NVIDIA_NVENC = "h264_nvenc"
    AMD_AMF = "h264_amf"
    INTEL_QSV = "h264_qsv"
    APPLE_VIDEOTOOLBOX = "h264_videotoolbox"
    SOFTWARE_X264 = "libx264"

    @classmethod
    def get_platform_encoders(cls) -> list[EncoderType]:
        import platform

        system = platform.system().lower()
        encoders = [cls.SOFTWARE_X264]
        if system == "darwin":
            encoders.insert(0, cls.APPLE_VIDEOTOOLBOX)
        elif system == "linux":
            encoders.insert(0, cls.NVIDIA_NVENC)
        elif system == "windows":
            encoders.insert(0, cls.NVIDIA_NVENC)
            encoders.insert(0, cls.AMD_AMF)
            encoders.insert(0, cls.INTEL_QSV)
        return encoders


@dataclass
class ProcessingResult:
    clip: ClipInfo
    output_path: Path | None
    duration: float
    frames_processed: int
    success: bool
    error: str | None = None
    used_encoder: str | None = None


class VideoProcessor:
    def __init__(self, output_dir: Path, options: ProcessingOptions, logger: logging.Logger | None = None):
        self.output_dir = output_dir
        self.options = options
        self.logger = logger or logging.getLogger(__name__)
        self._available_encoders = self._detect_encoders()

    def _detect_encoders(self) -> list[EncoderType]:
        """Probe ffmpeg encoders and order by global preference.

        Preference: VideoToolbox > NVENC > QSV > AMF > libx264.
        """
        available: list[EncoderType] = []
        try:
            result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
            text = (result.stdout or "").lower()
            preference = [
                EncoderType.APPLE_VIDEOTOOLBOX,
                EncoderType.NVIDIA_NVENC,
                EncoderType.INTEL_QSV,
                EncoderType.AMD_AMF,
                EncoderType.SOFTWARE_X264,
            ]
            for enc in preference:
                if enc == EncoderType.SOFTWARE_X264 or enc.value in text:
                    if enc not in available:
                        available.append(enc)
        except subprocess.SubprocessError:
            available = [EncoderType.SOFTWARE_X264]
        return available

    def _get_encoder_settings(self, encoder: EncoderType, thread_count: int | None = None) -> list[str]:
        mode_map = {
            ProcessingMode.QUALITY: "quality",
            ProcessingMode.BALANCED: "balanced",
            ProcessingMode.PERFORMANCE: "performance",
            ProcessingMode.LOW_MEMORY: "low_memory",
            ProcessingMode.MINIMAL: "minimal",
        }
        mode = mode_map[self.options.quality_mode]
        return build_encoder_settings(encoder.value, mode=mode, crf=self.options.crf, threads=thread_count)

    def _build_filter_complex(self, crop_overlap: int = 32) -> str:
        tile_processing = (
            f"[0:v:0]crop=iw-{crop_overlap}:ih-{crop_overlap}:0:0[tl];"
            f"[0:v:1]crop=iw-{crop_overlap}:ih-{crop_overlap}:{crop_overlap}:0[tr];"
            f"[0:v:2]crop=iw-{crop_overlap}:ih-{crop_overlap}:0:{crop_overlap}[bl];"
            f"[0:v:3]crop=iw-{crop_overlap}:ih-{crop_overlap}:{crop_overlap}:{crop_overlap}[br];"
            "[tl][tr]hstack=2[top];"
            "[bl][br]hstack=2[bottom];"
            "[top][bottom]vstack=2[full]"
        )
        width, height = self.options.output_resolution
        sf = getattr(self.options, "scale_filter", "lanczos")
        scaling = f"[full]scale={width}:{height}:flags={sf}[out]"
        return f"{tile_processing};{scaling}"

    def _create_concat_file(self, segments: list[SegmentInfo]) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            temp_file = f.name
            for segment in segments:
                for ts_file in segment.ts_files:
                    path_str = str(ts_file.absolute()).replace("\\", "/")
                    f.write(f"file '{path_str}'\n")
        return temp_file

    def process_clip(self, clip_result: ClipValidationResult) -> ProcessingResult:  # noqa: C901
        try:
            from typing import Any, cast
            opt = cast(Any, self.options)
            output_path = self.output_dir / f"{clip_result.clip.name}.mp4"
            concat_file = self._create_concat_file(clip_result.segments)

            import multiprocessing

            total_threads = multiprocessing.cpu_count()
            if self.options.quality_mode == ProcessingMode.MINIMAL:
                thread_count = 1
            elif self.options.quality_mode == ProcessingMode.LOW_MEMORY or self.options.low_memory:
                thread_count = max(1, total_threads // 2)
            else:
                thread_count = None

            for encoder in self._available_encoders:
                try:
                    cmd = ["ffmpeg", "-y"]
                    # best-effort decode acceleration
                    if getattr(opt, "decode", None) and str(opt.decode).lower() == "hw":
                        try:
                            import platform

                            sysname = platform.system().lower()
                            if sysname == "darwin":
                                cmd += ["-hwaccel", "videotoolbox"]
                            elif sysname == "linux":
                                cmd += ["-hwaccel", "cuda"]
                            elif sysname == "windows":
                                cmd += ["-hwaccel", "dxva2"]
                        except Exception as e:
                            logging.getLogger(__name__).debug("decode accel setup skipped: %s", e)

                    ws = getattr(opt, "window_seconds", None)
                    if ws and ws > 0:
                        cmd += ["-to", f"{ws}"]

                    cmd += [
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        concat_file,
                        "-filter_complex",
                        self._build_filter_complex(),
                        "-map",
                        "[out]",
                    ]
                    memory_opts: list[str] = []
                    if self.options.low_memory or self.options.quality_mode in [ProcessingMode.LOW_MEMORY, ProcessingMode.MINIMAL]:
                        memory_opts = ["-max_muxing_queue_size", "1024", "-tile-columns", "0", "-frame-parallel", "0"]
                    ft = getattr(opt, "filter_threads", None)
                    fct = getattr(opt, "filter_complex_threads", None)
                    if ft:
                        cmd += ["-filter_threads", str(ft)]
                    if fct:
                        cmd += ["-filter_complex_threads", str(fct)]
                    cmd.extend(self._get_encoder_settings(encoder, thread_count))
                    cmd.extend(memory_opts)
                    cmd.append(str(output_path))

                    creation_flags = CREATE_NO_WINDOW

                    # write command and capture logs
                    try:
                        output_path.with_suffix(output_path.suffix + ".cmd.txt").write_text(" ".join(cmd))
                    except Exception as e:
                        logging.getLogger(__name__).debug("failed to write cmd file: %s", e)

                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=creation_flags,
                    )
                    try:
                        output_path.with_suffix(output_path.suffix + ".log.txt").write_text((result.stdout or "") + "\n" + (result.stderr or ""))
                    except Exception as e:
                        logging.getLogger(__name__).debug("failed to write log file: %s", e)
                    _ = result
                    duration = clip_result.clip.duration
                    frames = sum(seg.frame_count for seg in clip_result.segments)
                    return ProcessingResult(
                        clip=clip_result.clip,
                        output_path=output_path,
                        duration=duration,
                        frames_processed=frames,
                        success=True,
                        used_encoder=encoder.value,
                    )
                except subprocess.SubprocessError as e:
                    last_error = str(e)
                    continue
            return ProcessingResult(
                clip=clip_result.clip,
                output_path=None,
                duration=0,
                frames_processed=0,
                success=False,
                error=last_error if "last_error" in locals() else "Unknown error",
            )
        finally:
            if "concat_file" in locals() and os.path.exists(concat_file):
                try:
                    os.remove(concat_file)
                except Exception as e:  # noqa: BLE001
                    logging.getLogger(__name__).debug("Failed to cleanup concat file: %s", e)
