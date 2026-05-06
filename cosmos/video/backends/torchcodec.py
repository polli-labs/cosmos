from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cosmos.video.backends.base import VideoBackendUnavailable
from cosmos.video.types import VideoDecodeError, VideoProbe

_DEVICE = "cpu"
_DIMENSION_ORDER = "NHWC"


class TorchCodecBackend:
    """Optional TorchCodec backend for CPU RGB frame extraction."""

    name = "torchcodec"

    def extract_index_frames(
        self,
        *,
        source_path: Path,
        indices: Sequence[int],
        frame_bytes: int,
        probe: VideoProbe,
    ) -> dict[int, bytes]:
        if not indices:
            return {}

        decoder = _video_decoder(source_path)
        try:
            batch = decoder.get_frames_at(list(indices))
        except Exception as exc:
            raise VideoDecodeError(
                f"TorchCodec failed while extracting frame indices {list(indices)!r} "
                f"from {source_path}: {exc}"
            ) from exc

        data = _batch_data(batch)
        if len(data) != len(indices):
            raise VideoDecodeError(
                f"TorchCodec returned {len(data)} frames for {len(indices)} requested indices "
                f"from {source_path}."
            )
        return {
            index: _tensor_rgb24_bytes(tensor, expected_bytes=frame_bytes)
            for index, tensor in zip(indices, data, strict=True)
        }

    def extract_time_frame(
        self,
        *,
        source_path: Path,
        time_seconds: float,
        frame_bytes: int,
        probe: VideoProbe,
    ) -> bytes:
        decoder = _video_decoder(source_path)
        try:
            batch = decoder.get_frames_played_at([time_seconds])
        except Exception as exc:
            raise VideoDecodeError(
                f"TorchCodec failed while extracting time {time_seconds:.6f}s "
                f"from {source_path}: {exc}"
            ) from exc

        data = _batch_data(batch)
        if len(data) != 1:
            raise VideoDecodeError(
                f"TorchCodec returned {len(data)} frames for time {time_seconds:.6f}s "
                f"from {source_path}."
            )
        return _tensor_rgb24_bytes(data[0], expected_bytes=frame_bytes)


def _video_decoder(source_path: Path) -> Any:
    video_decoder = _import_video_decoder()
    try:
        return video_decoder(
            str(source_path),
            device=_DEVICE,
            dimension_order=_DIMENSION_ORDER,
        )
    except Exception as exc:
        raise VideoDecodeError(f"TorchCodec could not open {source_path}: {exc}") from exc


def _import_video_decoder() -> Any:
    try:
        decoders = importlib.import_module("torchcodec.decoders")
    except ModuleNotFoundError as exc:
        missing = exc.name or "torchcodec"
        raise VideoBackendUnavailable(
            "TorchCodec video backend is unavailable. Install the optional extra with "
            "`uv sync --extra video-torchcodec`, make sure PyTorch is installed, and provide "
            "FFmpeg shared libraries visible to the dynamic loader. "
            f"Missing module: {missing}."
        ) from exc
    except (ImportError, OSError, RuntimeError) as exc:
        raise VideoBackendUnavailable(
            "TorchCodec video backend is unavailable because libtorchcodec could not load. "
            "Install compatible PyTorch/TorchCodec wheels and FFmpeg shared libraries visible "
            f"to the dynamic loader. Original error: {exc}"
        ) from exc
    return decoders.VideoDecoder


def _batch_data(batch: Any) -> Any:
    data = getattr(batch, "data", None)
    if data is None:
        raise VideoDecodeError("TorchCodec returned a frame batch without data.")
    return data


def _tensor_rgb24_bytes(tensor: Any, *, expected_bytes: int) -> bytes:
    try:
        contiguous = tensor.detach().cpu().contiguous()
        rgb24 = contiguous.numpy().tobytes()
    except ModuleNotFoundError as exc:
        if exc.name == "numpy":
            raise VideoBackendUnavailable(
                "TorchCodec RGB extraction requires NumPy. Install the optional extra with "
                "`uv sync --extra video-torchcodec` or force "
                "COSMOS_VIDEO_BACKEND=ffmpeg-cli."
            ) from exc
        raise
    except RuntimeError as exc:
        if "numpy" in str(exc).lower():
            raise VideoBackendUnavailable(
                "TorchCodec RGB extraction requires NumPy. Install the optional extra with "
                "`uv sync --extra video-torchcodec` or force "
                "COSMOS_VIDEO_BACKEND=ffmpeg-cli."
            ) from exc
        raise VideoDecodeError(f"TorchCodec tensor conversion failed: {exc}") from exc
    if len(rgb24) != expected_bytes:
        raise VideoDecodeError(
            f"TorchCodec produced {len(rgb24)} RGB bytes; expected {expected_bytes}. "
            "Check dimension_order=NHWC, probed dimensions, and video decode support."
        )
    return rgb24


__all__ = ["TorchCodecBackend"]
