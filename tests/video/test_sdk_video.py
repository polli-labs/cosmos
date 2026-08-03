from __future__ import annotations

import importlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from cosmos.ffmpeg.detect import resolve_ffmpeg_path
from cosmos.sdk import RgbFrame, VideoProbe
from cosmos.sdk.video import (
    VideoDecodeError,
    VideoProbeError,
    extract_frames_at_indices,
    extract_frames_at_times,
    probe_video,
)
from cosmos.video.backends.base import VideoBackendUnavailable


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(  # noqa: S603
            [resolve_ffmpeg_path(), "-version"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


ffmpeg_missing = not _ffmpeg_available()


def _pyav_available() -> bool:
    try:
        __import__("av")
        __import__("numpy")
    except ModuleNotFoundError:
        return False
    return True


pyav_missing = not _pyav_available()


def _torchcodec_available() -> bool:
    try:
        __import__("torch")
        importlib.import_module("torchcodec.decoders")
        __import__("numpy")
    except (ImportError, OSError, RuntimeError):
        return False
    return True


torchcodec_missing = not _torchcodec_available()


def _max_abs_rgb_delta(left: bytes, right: bytes) -> int:
    return max(
        (abs(left_byte - right_byte) for left_byte, right_byte in zip(left, right, strict=True)),
        default=0,
    )


def _make_tiny_video(tmp_path: Path) -> Path:
    src = tmp_path / "tiny.mp4"
    cmd = [
        resolve_ffmpeg_path(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=16x8:rate=5",
        "-frames:v",
        "5",
        "-c:v",
        "mpeg4",
        "-pix_fmt",
        "yuv420p",
        str(src),
    ]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    return src


def _make_long_gop_video(tmp_path: Path) -> Path:
    src = tmp_path / "long-gop.mp4"
    cmd = [
        resolve_ffmpeg_path(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=16x16:rate=60",
        "-frames:v",
        "540",
        "-c:v",
        "mpeg4",
        "-g",
        "180",
        "-bf",
        "0",
        "-sc_threshold",
        "0",
        "-q:v",
        "2",
        "-pix_fmt",
        "yuv420p",
        str(src),
    ]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    return src


class _FakeTorchCodecArray:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self) -> bytes:
        return self._payload


class _FakeTorchCodecTensor:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def detach(self) -> _FakeTorchCodecTensor:
        return self

    def cpu(self) -> _FakeTorchCodecTensor:
        return self

    def contiguous(self) -> _FakeTorchCodecTensor:
        return self

    def numpy(self) -> _FakeTorchCodecArray:
        return _FakeTorchCodecArray(self._payload)


class _FakeTorchCodecBatch:
    def __init__(self, payloads: list[bytes]) -> None:
        self.data = [_FakeTorchCodecTensor(payload) for payload in payloads]


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_probe_video_returns_typed_metadata(tmp_path: Path) -> None:
    src = _make_tiny_video(tmp_path)

    probe = probe_video(src)

    assert probe.source_path == src
    assert probe.width == 16
    assert probe.height == 8
    assert probe.fps == pytest.approx(5.0, rel=1e-2)
    assert probe.frame_count == 5
    assert probe.duration_seconds == pytest.approx(1.0, rel=1e-1)
    assert probe.codec_name is not None


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_extract_frames_at_indices_returns_rgb24_frames(tmp_path: Path) -> None:
    src = _make_tiny_video(tmp_path)

    frames = extract_frames_at_indices(src, [0, 2])

    assert len(frames) == 2
    assert frames[0].source_path == src
    assert frames[0].requested_index == 0
    assert frames[0].resolved_index == 0
    assert frames[0].requested_time_seconds is None
    assert frames[0].width == 16
    assert frames[0].height == 8
    assert len(frames[0].rgb24) == 16 * 8 * 3
    assert frames[1].requested_index == 2
    assert frames[1].resolved_time_seconds == pytest.approx(0.4, rel=1e-2)


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_extract_frames_at_indices_preserves_request_order_and_duplicates(
    tmp_path: Path,
) -> None:
    src = _make_tiny_video(tmp_path)

    frames = extract_frames_at_indices(src, [4, 0, 2, 2])

    assert [frame.requested_index for frame in frames] == [4, 0, 2, 2]
    assert [frame.resolved_index for frame in frames] == [4, 0, 2, 2]
    assert frames[2].rgb24 == frames[3].rgb24
    assert len({frame.rgb24 for frame in frames[:3]}) == 3


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_extract_frames_at_times_returns_rgb24_frames(tmp_path: Path) -> None:
    src = _make_tiny_video(tmp_path)

    frames = extract_frames_at_times(src, [0.0, 0.4])

    assert len(frames) == 2
    assert frames[0].requested_index is None
    assert frames[0].requested_time_seconds == 0.0
    assert frames[0].resolved_index is None
    assert frames[0].resolved_time_seconds is None
    assert len(frames[0].rgb24) == 16 * 8 * 3
    assert frames[1].requested_time_seconds == pytest.approx(0.4)


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_extract_frames_rejects_invalid_indices(tmp_path: Path) -> None:
    src = _make_tiny_video(tmp_path)

    with pytest.raises(ValueError, match="non-negative"):
        extract_frames_at_indices(src, [-1])

    with pytest.raises(ValueError, match="out of range"):
        extract_frames_at_indices(src, [5])


def test_probe_video_missing_file_error_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"

    with pytest.raises(VideoProbeError, match="Video source does not exist"):
        probe_video(missing)


def test_extract_frames_missing_file_error_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"

    with pytest.raises(VideoDecodeError, match="Video source does not exist"):
        extract_frames_at_indices(missing, [0])


def test_auto_backend_falls_back_when_pyav_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod
    from cosmos.video.backends.base import VideoBackendUnavailable

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class MissingPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise VideoBackendUnavailable("pyav missing")

    class FallbackBackend:
        name = "ffmpeg-cli"
        calls = 0

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            self.calls += 1
            return {0: b"\x01" * 12}

    fallback = FallbackBackend()
    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "auto")
    monkeypatch.setattr(decode_mod.sys, "platform", "darwin")
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", MissingPyAvBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", fallback)
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    frames = extract_frames_at_indices(src, [0])

    assert fallback.calls == 1
    assert frames[0].rgb24 == b"\x01" * 12


def test_auto_backend_prefers_ffmpeg_cli_on_linux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class UnexpectedPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise AssertionError("Linux auto backend should not try PyAV")

    class FallbackBackend:
        name = "ffmpeg-cli"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            return {0: b"\x03" * 12}

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "auto")
    monkeypatch.setattr(decode_mod.sys, "platform", "linux")
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", UnexpectedPyAvBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", FallbackBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    frames = extract_frames_at_indices(src, [0])

    assert frames[0].rgb24 == b"\x03" * 12


def test_auto_backend_does_not_hide_pyav_decode_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class BrokenPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise VideoDecodeError("pyav decode broke")

    class UnexpectedFallbackBackend:
        name = "ffmpeg-cli"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise AssertionError("auto should not hide PyAV decode failures")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "auto")
    monkeypatch.setattr(decode_mod.sys, "platform", "darwin")
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", BrokenPyAvBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", UnexpectedFallbackBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    with pytest.raises(VideoDecodeError, match="pyav decode broke"):
        extract_frames_at_indices(src, [0])


def test_forced_torchcodec_backend_uses_torchcodec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class TorchCodecBackend:
        name = "torchcodec"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            return {0: b"\x05" * 12}

    class UnexpectedFfmpegBackend:
        name = "ffmpeg-cli"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise AssertionError("forced torchcodec should not use FFmpeg CLI")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "torchcodec")
    monkeypatch.setattr(decode_mod, "_TORCHCODEC_BACKEND", TorchCodecBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", UnexpectedFfmpegBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    frames = extract_frames_at_indices(src, [0])

    assert frames[0].rgb24 == b"\x05" * 12


def test_forced_torchcodec_backend_missing_error_is_actionable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod
    from cosmos.video.backends.base import VideoBackendUnavailable

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class MissingTorchCodecBackend:
        name = "torchcodec"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise VideoBackendUnavailable("Install the optional extra")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "torchcodec")
    monkeypatch.setattr(decode_mod, "_TORCHCODEC_BACKEND", MissingTorchCodecBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    with pytest.raises(VideoDecodeError, match="optional extra"):
        extract_frames_at_indices(src, [0])


def test_pyav_time_extraction_rejects_untimed_frames_after_seek(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.pyav as pyav_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class FakeArray:
        def tobytes(self) -> bytes:
            return b"\x04" * 12

    class UntimedFrame:
        time = None
        pts = None
        time_base = None

        def to_ndarray(self, **kwargs: str) -> FakeArray:
            assert kwargs == {"format": "rgb24"}
            return FakeArray()

    class FakeStreams:
        video = [object()]

    class FakeContainer:
        streams = FakeStreams()

        def __enter__(self) -> FakeContainer:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def decode(self, *, video: int) -> list[UntimedFrame]:
            assert video == 0
            return [UntimedFrame(), UntimedFrame(), UntimedFrame()]

    class FakeAv:
        @staticmethod
        def open(_path: str) -> FakeContainer:
            return FakeContainer()

    monkeypatch.setattr(pyav_mod, "_import_av", lambda: FakeAv())
    monkeypatch.setattr(pyav_mod, "_seek_to_time", lambda *_args: True)

    backend = pyav_mod.PyAvBackend()
    probe = VideoProbe(source_path=src, width=2, height=2, frame_count=3, fps=5.0)

    with pytest.raises(VideoDecodeError, match="could not resolve decoded frame timestamps"):
        backend.extract_time_frame(
            source_path=src,
            time_seconds=10.0,
            frame_bytes=12,
            probe=probe,
        )


def test_unset_backend_defaults_to_ffmpeg_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class UnexpectedPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise AssertionError("unset backend should not try PyAV")

    class FallbackBackend:
        name = "ffmpeg-cli"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            return {0: b"\x02" * 12}

    monkeypatch.delenv("COSMOS_VIDEO_BACKEND", raising=False)
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", UnexpectedPyAvBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", FallbackBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    frames = extract_frames_at_indices(src, [0])

    assert frames[0].rgb24 == b"\x02" * 12


def test_blank_backend_env_defaults_to_ffmpeg_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class UnexpectedPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise AssertionError("blank backend should not try PyAV")

    class FallbackBackend:
        name = "ffmpeg-cli"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            return {0: b"\x04" * 12}

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "  ")
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", UnexpectedPyAvBackend())
    monkeypatch.setattr(decode_mod, "_FFMPEG_BACKEND", FallbackBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    frames = extract_frames_at_indices(src, [0])

    assert frames[0].rgb24 == b"\x04" * 12


def test_forced_pyav_backend_missing_error_is_actionable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.decode as decode_mod
    from cosmos.video.backends.base import VideoBackendUnavailable

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    class MissingPyAvBackend:
        name = "pyav"

        def extract_index_frames(self, **_kwargs: Any) -> dict[int, bytes]:
            raise VideoBackendUnavailable("Install the optional extra")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "pyav")
    monkeypatch.setattr(decode_mod, "_PYAV_BACKEND", MissingPyAvBackend())
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )

    with pytest.raises(VideoDecodeError, match="optional extra"):
        extract_frames_at_indices(src, [0])


def test_invalid_video_backend_env_is_actionable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "surprise")

    with pytest.raises(VideoDecodeError, match="COSMOS_VIDEO_BACKEND"):
        extract_frames_at_indices(
            src,
            [0],
            probe=VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
        )


def test_torchcodec_backend_preserves_rgb24_bytes_with_fake_decoder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.torchcodec as torchcodec_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    calls: list[dict[str, Any]] = []

    class FakeDecoder:
        def __init__(self, path: str, *, device: str, dimension_order: str) -> None:
            calls.append({"path": path, "device": device, "dimension_order": dimension_order})

        def get_frames_at(self, indices: list[int]) -> _FakeTorchCodecBatch:
            assert indices == [0, 2]
            return _FakeTorchCodecBatch([b"\x00" * 12, b"\x02" * 12])

        def get_frames_played_at(self, seconds: list[float]) -> _FakeTorchCodecBatch:
            assert seconds == [0.4]
            return _FakeTorchCodecBatch([b"\x04" * 12])

    monkeypatch.setattr(torchcodec_mod, "_import_video_decoder", lambda: FakeDecoder)
    backend = torchcodec_mod.TorchCodecBackend()
    probe = VideoProbe(source_path=src, width=2, height=2, frame_count=3, fps=5.0)

    index_frames = backend.extract_index_frames(
        source_path=src,
        indices=[0, 2],
        frame_bytes=12,
        probe=probe,
    )
    time_frame = backend.extract_time_frame(
        source_path=src,
        time_seconds=0.4,
        frame_bytes=12,
        probe=probe,
    )

    assert calls == [
        {"path": str(src), "device": "cpu", "dimension_order": "NHWC"},
        {"path": str(src), "device": "cpu", "dimension_order": "NHWC"},
    ]
    assert index_frames == {0: b"\x00" * 12, 2: b"\x02" * 12}
    assert time_frame == b"\x04" * 12


def test_torchcodec_import_error_is_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.torchcodec as torchcodec_mod

    def _raise_import_error(_module_name: str) -> object:
        raise ImportError("libavcodec.so could not be loaded")

    monkeypatch.setattr(torchcodec_mod.importlib, "import_module", _raise_import_error)

    with pytest.raises(VideoBackendUnavailable, match="libtorchcodec could not load"):
        torchcodec_mod._import_video_decoder()


def test_probe_video_uses_cosmos_ffprobe_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.probe as probe_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        payload = {
            "streams": [
                {
                    "width": 4,
                    "height": 3,
                    "avg_frame_rate": "30/1",
                    "nb_frames": "2",
                    "codec_name": "mpeg4",
                }
            ],
            "format": {"duration": "0.066667", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(probe_mod, "resolve_ffprobe_path", lambda: "/custom/ffprobe")
    monkeypatch.setattr(probe_mod.subprocess, "run", _fake_run)

    probe = probe_video(src)

    assert captured["cmd"][0] == "/custom/ffprobe"
    assert probe.width == 4
    assert probe.height == 3
    assert probe.frame_count == 2


def test_probe_video_wraps_ffprobe_resolver_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.probe as probe_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    def _raise_resolver_error() -> str:
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(probe_mod, "resolve_ffprobe_path", _raise_resolver_error)

    with pytest.raises(VideoProbeError, match="ffprobe could not be resolved"):
        probe_video(src)


def test_probe_video_wraps_permission_error_at_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.probe as probe_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    def _raise_permission_error(cmd: list[str], **_kwargs: Any) -> None:
        raise PermissionError(cmd[0])

    monkeypatch.setattr(probe_mod, "resolve_ffprobe_path", lambda: "/forbidden/ffprobe")
    monkeypatch.setattr(probe_mod.subprocess, "run", _raise_permission_error)

    with pytest.raises(
        VideoProbeError, match="ffprobe could not be launched at '/forbidden/ffprobe'"
    ) as error:
        probe_video(src)

    assert isinstance(error.value.__cause__, PermissionError)


def test_extract_frames_uses_cosmos_ffmpeg_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"\x00" * 12, stderr=b"")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=10.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [0])

    assert captured["cmd"][0] == "/custom/ffmpeg"
    assert frames == [
        RgbFrame(
            source_path=src,
            requested_index=0,
            requested_time_seconds=None,
            resolved_index=0,
            resolved_time_seconds=0.0,
            width=2,
            height=2,
            rgb24=b"\x00" * 12,
        )
    ]


def test_exported_extractors_wrap_ffmpeg_resolver_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    probe = VideoProbe(
        source_path=src,
        width=2,
        height=2,
        duration_seconds=1.0,
        frame_count=2,
        fps=1.0,
    )

    def _raise_resolver_error() -> str:
        raise RuntimeError("resolver unavailable")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", _raise_resolver_error)

    for extract in (
        lambda: extract_frames_at_indices(src, [0], probe=probe),
        lambda: extract_frames_at_times(src, [0.0], probe=probe),
    ):
        with pytest.raises(
            VideoDecodeError, match="ffmpeg could not be resolved.*resolver unavailable"
        ) as error:
            extract()
        assert isinstance(error.value.__cause__, RuntimeError)


def test_exported_extractor_wraps_permission_error_at_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    probe = VideoProbe(source_path=src, width=2, height=2, frame_count=1, fps=1.0)

    def _raise_permission_error(cmd: list[str], **_kwargs: Any) -> None:
        raise PermissionError(cmd[0])

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/forbidden/ffmpeg")
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _raise_permission_error)

    with pytest.raises(
        VideoDecodeError, match="ffmpeg could not be launched at '/forbidden/ffmpeg'"
    ) as error:
        extract_frames_at_indices(src, [0], probe=probe)

    assert isinstance(error.value.__cause__, PermissionError)


def test_extract_frames_wraps_ffmpeg_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")

    def _fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        timeout = kwargs.get("timeout")
        assert isinstance(timeout, int | float)
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setenv("COSMOS_VIDEO_FFMPEG_TIMEOUT", "1.5")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=2, fps=1.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    with pytest.raises(VideoDecodeError, match="ffmpeg timed out after 1.5s"):
        extract_frames_at_indices(src, [0])


def test_extract_frames_at_indices_batches_unique_sparse_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []
    frame_zero = b"\x00" * 12
    frame_two = b"\x02" * 12

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=frame_zero + frame_two, stderr=b"")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=3, fps=10.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [2, 0, 2])

    assert len(captured) == 1
    assert captured[0][0] == "/custom/ffmpeg"
    assert "select=eq(n\\,0)+eq(n\\,2)" in captured[0]
    assert captured[0][captured[0].index("-fps_mode") + 1] == "passthrough"
    assert captured[0][captured[0].index("-frames:v") + 1] == "2"
    assert [frame.requested_index for frame in frames] == [2, 0, 2]
    assert [frame.resolved_index for frame in frames] == [2, 0, 2]
    assert [frame.rgb24 for frame in frames] == [frame_two, frame_zero, frame_two]


def test_extract_frames_at_indices_chunks_large_select_expressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        select_arg = next(part for part in cmd if part.startswith("select="))
        selected = [int(match) for match in re.findall(r"eq\(n\\,(\d+)\)", select_arg)]
        stdout = b"".join(bytes([index]) * 12 for index in selected)
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=b"")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "_MAX_SELECT_EXPRESSION_CHARS", 18)
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=31, fps=10.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [20, 0, 10, 20])

    assert len(captured) == 2
    assert [cmd[cmd.index("-frames:v") + 1] for cmd in captured] == ["2", "1"]
    assert [frame.requested_index for frame in frames] == [20, 0, 10, 20]
    assert [frame.rgb24 for frame in frames] == [
        b"\x14" * 12,
        b"\x00" * 12,
        b"\x0a" * 12,
        b"\x14" * 12,
    ]


def test_extract_frames_at_indices_uses_seek_windows_for_late_sparse_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []
    frame_900 = b"\x84" * 12
    frame_1080 = b"\x38" * 12

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=frame_900 + frame_1080, stderr=b"")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        ffmpeg_mod,
        "_packet_timestamps_for_source",
        lambda _path: tuple(index / 60 for index in range(1200)),
    )
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1200, fps=60.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [900, 1080])

    assert len(captured) == 1
    assert captured[0][captured[0].index("-ss") + 1] == "15.000000000"
    assert "select=eq(n\\,0)+eq(n\\,180)" in captured[0]
    assert [frame.rgb24 for frame in frames] == [frame_900, frame_1080]


def test_extract_frames_at_indices_uses_seek_windows_for_split_sparse_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []
    frame_zero = b"\x00" * 12
    frame_900 = b"\x84" * 12
    frame_1080 = b"\x38" * 12

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        start_time = cmd[cmd.index("-ss") + 1]
        if start_time == "0.000000000":
            return subprocess.CompletedProcess(cmd, 0, stdout=frame_zero, stderr=b"")
        if start_time == "15.000000000":
            return subprocess.CompletedProcess(cmd, 0, stdout=frame_900 + frame_1080, stderr=b"")
        raise AssertionError(f"unexpected seek start: {start_time}")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(
        ffmpeg_mod,
        "_packet_timestamps_for_source",
        lambda _path: tuple(index / 60 for index in range(1200)),
    )
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1200, fps=60.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [0, 900, 1080])

    assert len(captured) == 2
    assert [cmd[cmd.index("-ss") + 1] for cmd in captured] == ["0.000000000", "15.000000000"]
    assert "select=eq(n\\,0)" in captured[0]
    assert "select=eq(n\\,0)+eq(n\\,180)" in captured[1]
    assert [frame.rgb24 for frame in frames] == [frame_zero, frame_900, frame_1080]


def test_extract_frames_at_indices_keeps_full_scan_for_dense_from_start_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []
    requested = [0, 180, 360, 540, 720, 900, 1080]

    def _fake_timestamps(_path: Path) -> tuple[float, ...]:
        raise AssertionError("dense from-start requests should not probe packet timestamps")

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        select_arg = next(part for part in cmd if part.startswith("select="))
        selected = [int(match) for match in re.findall(r"eq\(n\\,(\d+)\)", select_arg)]
        stdout = b"".join(bytes([index % 256]) * 12 for index in selected)
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=b"")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(ffmpeg_mod, "_packet_timestamps_for_source", _fake_timestamps)
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1200, fps=60.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, requested)

    assert len(captured) == 1
    assert "-ss" not in captured[0]
    assert [frame.rgb24 for frame in frames] == [bytes([index % 256]) * 12 for index in requested]


def test_extract_frames_at_indices_falls_back_when_seek_timestamps_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod
    import cosmos.video.decode as decode_mod

    src = tmp_path / "tiny.mp4"
    src.write_bytes(b"placeholder")
    captured: list[list[str]] = []
    frame_1080 = b"\x38" * 12

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=frame_1080, stderr=b"")

    def _raise_timestamps(_path: Path) -> tuple[float, ...]:
        raise VideoDecodeError("packet timestamps unavailable")

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    monkeypatch.setattr(ffmpeg_mod, "resolve_ffmpeg_path", lambda: "/custom/ffmpeg")
    monkeypatch.setattr(ffmpeg_mod, "_packet_timestamps_for_source", _raise_timestamps)
    monkeypatch.setattr(
        decode_mod,
        "probe_video",
        lambda _path: VideoProbe(source_path=src, width=2, height=2, frame_count=1200, fps=60.0),
    )
    monkeypatch.setattr(ffmpeg_mod.subprocess, "run", _fake_run)

    frames = extract_frames_at_indices(src, [1080])

    assert len(captured) == 1
    assert "-ss" not in captured[0]
    assert frames[0].rgb24 == frame_1080


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
def test_extract_frames_at_indices_seek_window_matches_scan_for_non_keyframe_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.ffmpeg_cli as ffmpeg_mod

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    src = _make_long_gop_video(tmp_path)
    probe = probe_video(src)
    requested = [481, 500]
    frame_bytes = probe.width * probe.height * 3
    assert ffmpeg_mod._plan_seek_groups(requested) == [requested]

    scan = ffmpeg_mod._extract_scan_index_frames(
        source_path=src,
        indices=requested,
        frame_bytes=frame_bytes,
    )
    frames = extract_frames_at_indices(src, requested, probe=probe)

    assert [frame.rgb24 for frame in frames] == [scan[index] for index in requested]


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
@pytest.mark.skipif(pyav_missing, reason="PyAV extra not available")
def test_pyav_backend_preserves_indices_and_roughly_matches_ffmpeg_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.backends.pyav as pyav_mod

    src = _make_long_gop_video(tmp_path)
    probe = probe_video(src)
    requested = [0, 181, 481, 500]
    frame_bytes = probe.width * probe.height * 3

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    ffmpeg_frames = extract_frames_at_indices(src, requested, probe=probe)
    ffmpeg_time_frames = extract_frames_at_times(src, [0.0, 3.0], probe=probe)

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "pyav")
    pyav_frames = extract_frames_at_indices(src, requested, probe=probe)
    pyav_time_frames = extract_frames_at_times(src, [0.0, 3.0], probe=probe)
    pyav_scan = pyav_mod._extract_scan_index_frames(
        source_path=src,
        indices=requested,
        frame_bytes=frame_bytes,
    )

    assert [frame.requested_index for frame in pyav_frames] == requested
    assert [frame.rgb24 for frame in pyav_frames] == [pyav_scan[index] for index in requested]
    assert all(
        _max_abs_rgb_delta(pyav_frame.rgb24, ffmpeg_frame.rgb24) <= 4
        for pyav_frame, ffmpeg_frame in zip(pyav_frames, ffmpeg_frames, strict=True)
    )
    assert all(
        _max_abs_rgb_delta(pyav_frame.rgb24, ffmpeg_frame.rgb24) <= 4
        for pyav_frame, ffmpeg_frame in zip(pyav_time_frames, ffmpeg_time_frames, strict=True)
    )


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not available")
@pytest.mark.skipif(torchcodec_missing, reason="TorchCodec extra not available")
def test_torchcodec_backend_preserves_indices_and_roughly_matches_ffmpeg_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _make_long_gop_video(tmp_path)
    probe = probe_video(src)
    requested = [0, 181, 481, 500]

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "ffmpeg-cli")
    ffmpeg_frames = extract_frames_at_indices(src, requested, probe=probe)
    ffmpeg_time_frames = extract_frames_at_times(src, [0.0, 3.0], probe=probe)

    monkeypatch.setenv("COSMOS_VIDEO_BACKEND", "torchcodec")
    torchcodec_frames = extract_frames_at_indices(src, requested, probe=probe)
    torchcodec_time_frames = extract_frames_at_times(src, [0.0, 3.0], probe=probe)

    assert [frame.requested_index for frame in torchcodec_frames] == requested
    assert all(
        _max_abs_rgb_delta(torchcodec_frame.rgb24, ffmpeg_frame.rgb24) <= 4
        for torchcodec_frame, ffmpeg_frame in zip(
            torchcodec_frames,
            ffmpeg_frames,
            strict=True,
        )
    )
    assert all(
        _max_abs_rgb_delta(torchcodec_frame.rgb24, ffmpeg_frame.rgb24) <= 4
        for torchcodec_frame, ffmpeg_frame in zip(
            torchcodec_time_frames,
            ffmpeg_time_frames,
            strict=True,
        )
    )
