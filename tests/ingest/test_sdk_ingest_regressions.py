from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from cosmos.ingest.adapter import ClipDescriptor
from cosmos.ingest.manifest import ClipInfo, Position
from cosmos.ingest.processor import ProcessingResult, VideoProcessor
from cosmos.sdk.ingest import IngestOptions, _emit_clip_provenance, ingest

SAMPLE_MANIFEST = """<?xml version="1.0"?>
<Clip_Manifest>
    <_1 Name="CLIP1" Epoch="1700000000.0" Pos="0H/0M/3.8S/"
        InIdx="0" OutIdx="100" Lock="1"
        InStr="14:26:40.000 11/14/2023"/>
</Clip_Manifest>
"""


def _clip_descriptor(
    *,
    name: str,
    start_time_sec: float,
    end_time_sec: float | None,
    frame_start: int,
    frame_end: int,
) -> ClipDescriptor:
    return ClipDescriptor(
        name=name,
        start_time_sec=start_time_sec,
        end_time_sec=end_time_sec,
        frame_start=frame_start,
        frame_end=frame_end,
    )


def _clip_info(*, name: str, duration: float, frame_count: int) -> ClipInfo:
    end_epoch = duration if duration > 0 else None
    end_pos = Position(0, 0, duration) if duration > 0 else None
    return ClipInfo(
        name=name,
        start_epoch=0.0,
        end_epoch=end_epoch,
        start_pos=Position(0, 0, 0.0),
        end_pos=end_pos,
        start_idx=0,
        end_idx=frame_count,
        start_time=None,
    )


def test_ingest_run_provenance_uses_detected_manifest_for_cosm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()
    manifest_path = input_dir / "manifest.xml"
    manifest_path.write_text(SAMPLE_MANIFEST)

    # Avoid host/tool preflight concerns in this unit test.
    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("cosmos.ingest.adapters.cosm._default_validate_system", lambda *_args: [])
    # Keep this unit test independent from host ffmpeg availability.
    monkeypatch.setattr(ingest_mod.VideoProcessor, "_detect_encoders", lambda _self: [])

    captured: dict[str, object] = {}

    def _capture_run_emit(**kwargs):
        captured.update(kwargs)
        return ("run-id", output_dir / "cosmos_ingest_run.v1.json")

    monkeypatch.setattr(ingest_mod, "emit_ingest_run", _capture_run_emit)

    _ = ingest(
        input_dir,
        output_dir,
        manifest=None,
        options=IngestOptions(dry_run=True),
    )

    assert captured["manifest_path"] == manifest_path
    options = captured["options"]
    assert isinstance(options, dict)
    options = cast(dict[str, object], options)
    assert options["adapter"] == "cosm"


def test_emit_clip_provenance_does_not_double_count_end_time(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    output_mp4 = tmp_path / "clip.mp4"
    output_mp4.write_bytes(b"ok")

    captured: dict[str, object] = {}

    def _capture_clip_emit(**kwargs):
        captured.update(kwargs)
        return tmp_path / "clip.mp4.cosmos_clip.v1.json"

    monkeypatch.setattr(ingest_mod, "emit_clip_artifact", _capture_clip_emit)

    clip = _clip_descriptor(
        name="CLIP1",
        start_time_sec=10.0,
        end_time_sec=20.0,
        frame_start=100,
        frame_end=200,
    )
    clip_result = SimpleNamespace(clip=SimpleNamespace(duration=10.0, frame_count=100))
    spec = SimpleNamespace(filter_complex="dummy-filter")
    result = ProcessingResult(
        clip=_clip_info(name="CLIP1", duration=10.0, frame_count=100),
        output_path=output_mp4,
        duration=10.0,
        frames_processed=100,
        success=True,
        used_encoder="libx264",
    )

    _emit_clip_provenance(
        ingest_run_id="run-id",
        clip=clip,
        clip_result=clip_result,
        spec=spec,
        res=result,
        options=IngestOptions(crf=23),
        processor=cast(VideoProcessor, SimpleNamespace()),
    )

    assert captured["time_ms"] == (10000.0, 20000.0)


def test_emit_clip_provenance_probes_output_duration_when_unknown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    output_mp4 = tmp_path / "clip.mp4"
    output_mp4.write_bytes(b"ok")

    captured: dict[str, object] = {}

    def _capture_clip_emit(**kwargs):
        captured.update(kwargs)
        return tmp_path / "clip.mp4.cosmos_clip.v1.json"

    monkeypatch.setattr(ingest_mod, "emit_clip_artifact", _capture_clip_emit)
    monkeypatch.setattr(ingest_mod, "ffprobe_video", lambda _p: {"duration_sec": 7.25})

    clip = _clip_descriptor(
        name="CLIP2",
        start_time_sec=5.0,
        end_time_sec=None,
        frame_start=1,
        frame_end=10,
    )
    clip_result = SimpleNamespace(clip=SimpleNamespace(duration=0.0, frame_count=10))
    spec = SimpleNamespace(filter_complex="dummy-filter")
    result = ProcessingResult(
        clip=_clip_info(name="CLIP2", duration=0.0, frame_count=10),
        output_path=output_mp4,
        duration=0.0,
        frames_processed=10,
        success=True,
        used_encoder="libx264",
    )

    _emit_clip_provenance(
        ingest_run_id="run-id",
        clip=clip,
        clip_result=clip_result,
        spec=spec,
        res=result,
        options=IngestOptions(crf=23),
        processor=cast(VideoProcessor, SimpleNamespace()),
    )

    assert captured["time_ms"] == (5000.0, 12250.0)
