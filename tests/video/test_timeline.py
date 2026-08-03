from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from cosmos.ffmpeg.detect import resolve_ffmpeg_path, resolve_ffprobe_path
from cosmos.sdk import VideoFrameTimeline, probe_video_timeline
from cosmos.sdk.video import VideoProbeError
from cosmos.video.timeline import _parse_video_frame_timeline_payload


def _timeline_payload(
    frames: list[object],
    *,
    time_base: object = "1/15360",
) -> dict[str, object]:
    return {
        "streams": [{"time_base": time_base}],
        "frames": frames,
    }


def _make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"placeholder")
    return source


def _video_tools_available() -> bool:
    for executable in (resolve_ffmpeg_path(), resolve_ffprobe_path()):
        try:
            subprocess.run(  # noqa: S603
                [executable, "-version"],
                check=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
    return True


video_tools_missing = not _video_tools_available()


def test_parser_preserves_emitted_frame_order_and_uses_actual_pts(
    tmp_path: Path,
) -> None:
    source = _make_source(tmp_path)
    payload = _timeline_payload(
        [
            {"pts": "100", "best_effort_timestamp": "1000", "pkt_dts": "100"},
            {"pts": "104", "best_effort_timestamp": "1004", "pkt_dts": "109"},
            {"pts": "109", "best_effort_timestamp": "1009", "pkt_dts": "104"},
        ],
        time_base="1/90000",
    )

    timeline = _parse_video_frame_timeline_payload(payload, source_path=source)

    assert timeline == VideoFrameTimeline(
        source_path=source,
        time_base_numerator=1,
        time_base_denominator=90000,
        pts_ticks=(100, 104, 109),
    )


def test_parser_accepts_pts_without_best_effort_timestamp(
    tmp_path: Path,
) -> None:
    source = _make_source(tmp_path)
    payload = _timeline_payload([{"pts": "100"}, {"pts": "104"}, {"pts": 109}])

    timeline = _parse_video_frame_timeline_payload(payload, source_path=source)

    assert timeline.pts_ticks == (100, 104, 109)


def test_parser_rejects_missing_pts_even_when_best_effort_timestamp_exists(
    tmp_path: Path,
) -> None:
    source = _make_source(tmp_path)
    payload = _timeline_payload([{"best_effort_timestamp": "1"}])

    with pytest.raises(VideoProbeError, match="no PTS identity"):
        _parse_video_frame_timeline_payload(payload, source_path=source)


def test_parser_does_not_hide_malformed_pts_with_best_effort_timestamp(
    tmp_path: Path,
) -> None:
    source = _make_source(tmp_path)
    payload = _timeline_payload([{"pts": "1.5", "best_effort_timestamp": "1"}])

    with pytest.raises(VideoProbeError, match=r"non-integral pts='1.5'"):
        _parse_video_frame_timeline_payload(payload, source_path=source)


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        ([{}], "no PTS identity"),
        ([{"pts": "N/A", "best_effort_timestamp": "1"}], "no PTS identity"),
        ([{"pts": 1.0, "best_effort_timestamp": "1"}], "non-integral pts=1.0"),
        ([{"pts": True}], "non-integral pts=True"),
        (
            [{"pts": "1"}, {"pts": "1"}],
            "duplicate PTS tick 1 after 1",
        ),
        (
            [{"pts": "2"}, {"pts": "1"}],
            "nonmonotonic PTS tick 1 after 2",
        ),
    ],
)
def test_parser_rejects_unusable_frame_identities(
    tmp_path: Path,
    frames: list[object],
    message: str,
) -> None:
    source = _make_source(tmp_path)

    with pytest.raises(VideoProbeError, match=message):
        _parse_video_frame_timeline_payload(_timeline_payload(frames), source_path=source)


@pytest.mark.parametrize("time_base", [None, "", "1", "0/1", "1/0", "1.0/90000"])
def test_parser_rejects_missing_or_invalid_stream_time_base(
    tmp_path: Path,
    time_base: object,
) -> None:
    source = _make_source(tmp_path)

    with pytest.raises(VideoProbeError, match="time_base"):
        _parse_video_frame_timeline_payload(
            _timeline_payload([{"pts": "0"}], time_base=time_base),
            source_path=source,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "invalid timeline payload"),
        ({}, "No video stream"),
        ({"streams": [None], "frames": []}, "invalid video stream"),
        ({"streams": [{"time_base": "1/1"}]}, "No decoded video frames"),
        ({"streams": [{"time_base": "1/1"}], "frames": [None]}, "invalid decoded frame"),
    ],
)
def test_parser_rejects_malformed_payloads(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    source = _make_source(tmp_path)

    with pytest.raises(VideoProbeError, match=message):
        _parse_video_frame_timeline_payload(payload, source_path=source)


def test_probe_video_timeline_uses_shared_resolver_and_requests_actual_pts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs == {
            "check": True,
            "capture_output": True,
            "text": True,
            "timeout": None,
        }
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                _timeline_payload(
                    [
                        {"pts": "0"},
                        {"pts": "512"},
                    ],
                    time_base="1/2560",
                )
            ),
            stderr="",
        )

    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", lambda: "/shared/ffprobe")
    monkeypatch.setattr(timeline_module.subprocess, "run", fake_run)

    timeline = probe_video_timeline(source)

    assert timeline.pts_ticks == (0, 512)
    assert calls == [
        [
            "/shared/ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_frames",
            "-show_entries",
            "stream=time_base:frame=pts",
            "-of",
            "json",
            str(source),
        ]
    ]


def test_probe_video_timeline_wraps_resolver_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)

    def fail_resolver() -> str:
        raise RuntimeError("resolver broke")

    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", fail_resolver)

    with pytest.raises(VideoProbeError, match="Could not resolve ffprobe.*resolver broke"):
        probe_video_timeline(source)


def test_probe_video_timeline_wraps_process_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)
    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", lambda: "/shared/ffprobe")

    def fail_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(7, command, stderr="bad media")

    monkeypatch.setattr(timeline_module.subprocess, "run", fail_run)

    with pytest.raises(VideoProbeError, match="exit code 7: bad media"):
        probe_video_timeline(source)


def test_probe_video_timeline_wraps_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)
    monkeypatch.setenv("COSMOS_VIDEO_FFMPEG_TIMEOUT", "2.5")
    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", lambda: "/shared/ffprobe")

    def fail_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] == 2.5
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(timeline_module.subprocess, "run", fail_run)

    with pytest.raises(
        VideoProbeError,
        match="ffprobe timed out after 2.5s while reading the decoded frame timeline",
    ):
        probe_video_timeline(source)


def test_probe_video_timeline_wraps_permission_error_at_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)
    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", lambda: "/forbidden/ffprobe")

    def fail_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise PermissionError(command[0])

    monkeypatch.setattr(timeline_module.subprocess, "run", fail_run)

    with pytest.raises(
        VideoProbeError, match="ffprobe could not be launched at '/forbidden/ffprobe'"
    ) as error:
        probe_video_timeline(source)

    assert isinstance(error.value.__cause__, PermissionError)


def test_probe_video_timeline_rejects_malformed_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cosmos.video.timeline as timeline_module

    source = _make_source(tmp_path)
    monkeypatch.setattr(timeline_module, "resolve_ffprobe_path", lambda: "/shared/ffprobe")
    monkeypatch.setattr(
        timeline_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="{", stderr=""),
    )

    with pytest.raises(VideoProbeError, match="invalid timeline JSON"):
        probe_video_timeline(source)


def test_probe_video_timeline_is_exported_from_public_modules() -> None:
    from cosmos import sdk, video
    from cosmos.sdk import video as sdk_video

    assert sdk.probe_video_timeline is probe_video_timeline
    assert sdk_video.probe_video_timeline is probe_video_timeline
    assert video.probe_video_timeline is probe_video_timeline


@pytest.mark.skipif(video_tools_missing, reason="ffmpeg/ffprobe not available")
def test_probe_video_timeline_reads_exact_pts_from_real_b_frame_video(tmp_path: Path) -> None:
    source = tmp_path / "b-frames.mp4"
    subprocess.run(  # noqa: S603
        [
            resolve_ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=32x16:rate=5",
            "-frames:v",
            "10",
            "-c:v",
            "mpeg4",
            "-g",
            "10",
            "-bf",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    raw_timeline = subprocess.run(  # noqa: S603
        [
            resolve_ffprobe_path(),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_frames",
            "-show_entries",
            "stream=time_base:frame=pts,pict_type",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    raw_payload: Any = json.loads(raw_timeline.stdout)
    assert isinstance(raw_payload, dict)
    raw_payload_mapping = cast(dict[str, object], raw_payload)
    raw_streams = raw_payload_mapping.get("streams")
    raw_frames = raw_payload_mapping.get("frames")
    assert isinstance(raw_streams, list) and len(raw_streams) == 1
    assert isinstance(raw_frames, list) and len(raw_frames) == 10
    assert isinstance(raw_streams[0], dict)
    raw_stream = cast(dict[str, object], raw_streams[0])
    raw_time_base = raw_stream.get("time_base")
    assert isinstance(raw_time_base, str)
    numerator_raw, denominator_raw = raw_time_base.split("/", 1)

    raw_pts: list[int] = []
    raw_frame_types: list[str] = []
    for raw_frame_value in raw_frames:
        assert isinstance(raw_frame_value, dict)
        raw_frame = cast(dict[str, object], raw_frame_value)
        pts_value = raw_frame.get("pts")
        pict_type = raw_frame.get("pict_type")
        assert isinstance(pts_value, int) and not isinstance(pts_value, bool)
        assert isinstance(pict_type, str)
        raw_pts.append(pts_value)
        raw_frame_types.append(pict_type)

    timeline = probe_video_timeline(source)

    assert "B" in raw_frame_types
    assert timeline.source_path == source
    assert timeline.time_base_numerator == int(numerator_raw)
    assert timeline.time_base_denominator == int(denominator_raw)
    assert timeline.pts_ticks == tuple(raw_pts)
