from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from cosmos.ingest.processor import ProcessingResult
from cosmos.sdk.ingest import IngestOptions, _emit_clip_provenance, ingest

SAMPLE_MANIFEST = """<?xml version="1.0"?>
<Clip_Manifest>
    <_1 Name="CLIP1" Epoch="1700000000.0" Pos="0H/0M/3.8S/"
        InIdx="0" OutIdx="100" Lock="1"
        InStr="14:26:40.000 11/14/2023"/>
</Clip_Manifest>
"""


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
    assert captured["options"]["adapter"] == "cosm"


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

    clip = SimpleNamespace(
        name="CLIP1",
        start_time_sec=10.0,
        end_time_sec=20.0,
        frame_start=100,
        frame_end=200,
    )
    clip_result = SimpleNamespace(clip=SimpleNamespace(duration=10.0, frame_count=100))
    spec = SimpleNamespace(filter_complex="dummy-filter")
    result = ProcessingResult(
        clip=SimpleNamespace(duration=10.0, frame_count=100),
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
        processor=SimpleNamespace(),
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

    clip = SimpleNamespace(
        name="CLIP2",
        start_time_sec=5.0,
        end_time_sec=None,
        frame_start=1,
        frame_end=10,
    )
    clip_result = SimpleNamespace(clip=SimpleNamespace(duration=0.0, frame_count=10))
    spec = SimpleNamespace(filter_complex="dummy-filter")
    result = ProcessingResult(
        clip=SimpleNamespace(duration=0.0, frame_count=10),
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
        processor=SimpleNamespace(),
    )

    assert captured["time_ms"] == (5000.0, 12250.0)
