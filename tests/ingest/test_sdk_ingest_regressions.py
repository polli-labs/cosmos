from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from cosmos.ingest.adapter import ClipDescriptor, FfmpegInputSpec
from cosmos.ingest.manifest import ClipInfo, Position
from cosmos.ingest.processor import ProcessingResult, VideoProcessor
from cosmos.ingest.validation import (
    ClipValidationResult,
    SegmentInfo,
    ValidationIssue,
    ValidationLevel,
)
from cosmos.sdk.ingest import (
    IngestOptions,
    IngestSystemPreflightError,
    _emit_clip_provenance,
    ingest,
)

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


class _PreflightFailingAdapter:
    name = "fake-preflight"

    def validate_system(self, _output_dir: Path) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                level=ValidationLevel.WARNING,
                message="output directory is nearly full",
                context="available_space=512M",
                help_text="free space before production ingest",
            ),
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message="FFmpeg not found or not working",
                context="COSMOS_FFMPEG=/missing/ffmpeg",
                help_text="Install FFmpeg and ensure it is on PATH",
            ),
        ]

    def discover_clips(self, _input_dir: Path) -> list[ClipDescriptor]:
        raise AssertionError("fatal system preflight should stop before clip discovery")


class _SingleClipAdapter:
    name = "single-clip"

    def validate_system(self, _output_dir: Path) -> list[ValidationIssue]:
        return []

    def discover_clips(self, _input_dir: Path) -> list[ClipDescriptor]:
        return [
            _clip_descriptor(
                name="CLIP1",
                start_time_sec=0.0,
                end_time_sec=1.0,
                frame_start=0,
                frame_end=30,
            )
        ]

    def validate_clip(
        self,
        clip: ClipDescriptor,
        input_dir: Path,
        _output_dir: Path,
    ) -> ClipValidationResult:
        return ClipValidationResult(
            clip=_clip_info(name=clip.name, duration=1.0, frame_count=30),
            segments=[
                SegmentInfo(
                    directory=input_dir,
                    start_time=0.0,
                    frame_timestamps=[0.0, 1.0],
                    ts_files=[input_dir / "segment.ts"],
                )
            ],
            missing_segments=[],
            issues=[],
            estimated_size=1,
        )

    def build_ffmpeg_spec(
        self,
        _clip: ClipDescriptor,
        _validation: ClipValidationResult,
        _output_dir: Path,
        output_resolution: tuple[int, int],
        scale_filter: str,
    ) -> FfmpegInputSpec:
        assert output_resolution == (3840, 2160)
        assert scale_filter
        return FfmpegInputSpec(
            input_args=["-i", "input.mp4"],
            filter_complex="scale=128:128",
            output_stem="clip1",
        )


class _TempManifestAdapter(_SingleClipAdapter):
    name = "temp-manifest"

    def build_ffmpeg_spec(
        self,
        _clip: ClipDescriptor,
        _validation: ClipValidationResult,
        _output_dir: Path,
        output_resolution: tuple[int, int],
        scale_filter: str,
    ) -> FfmpegInputSpec:
        _ = (output_resolution, scale_filter)
        temp_manifest = _output_dir / "adapter-concat.txt"
        temp_manifest.parent.mkdir(parents=True, exist_ok=True)
        temp_manifest.write_text("file 'segment.ts'\n")
        return FfmpegInputSpec(
            input_args=["-f", "concat", "-safe", "0", "-i", str(temp_manifest)],
            filter_complex="scale=128:128",
            output_stem="clip1",
            temp_files=[str(temp_manifest)],
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("quality_mode", "turbo"),
        ("scale_filter", "nearest"),
        ("decode", "gpu"),
    ],
)
def test_ingest_rejects_invalid_option_strings(
    tmp_path: Path,
    monkeypatch,
    field: str,
    value: str,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod,
        "resolve_adapter",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid options should stop before adapter resolution")
        ),
    )

    if field == "quality_mode":
        options = IngestOptions(quality_mode=value)
    elif field == "scale_filter":
        options = IngestOptions(scale_filter=value)
    elif field == "decode":
        options = IngestOptions(decode=value)
    else:
        raise AssertionError(f"unhandled field under test: {field}")

    with pytest.raises(ValueError) as exc_info:
        ingest(
            input_dir,
            output_dir,
            manifest=None,
            options=options,
        )

    message = str(exc_info.value)
    assert field in message
    assert repr(value) in message
    assert "Accepted values:" in message


@pytest.mark.parametrize("dry_run", [False, True])
def test_adapter_error_preflight_stops_before_processing(
    tmp_path: Path,
    monkeypatch,
    dry_run: bool,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod,
        "resolve_adapter",
        lambda *_args, **_kwargs: _PreflightFailingAdapter(),
    )
    monkeypatch.setattr(
        ingest_mod.VideoProcessor,
        "__init__",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fatal system preflight should stop before processor construction")
        ),
    )

    with pytest.raises(IngestSystemPreflightError) as exc_info:
        ingest(
            input_dir,
            output_dir,
            manifest=None,
            options=IngestOptions(dry_run=dry_run),
        )

    message = str(exc_info.value)
    assert "fake-preflight" in message
    assert "warning: output directory is nearly full" in message
    assert "error: FFmpeg not found or not working" in message
    assert "COSMOS_FFMPEG=/missing/ffmpeg" in message
    assert "Install FFmpeg and ensure it is on PATH" in message


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


def test_ingest_real_run_fails_when_clip_artifact_provenance_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod, "resolve_adapter", lambda *_args, **_kwargs: _SingleClipAdapter()
    )
    monkeypatch.setattr(ingest_mod.VideoProcessor, "_detect_encoders", lambda _self: [])
    monkeypatch.setattr(
        ingest_mod,
        "emit_ingest_run",
        lambda **_kwargs: ("run-id", output_dir / "cosmos_ingest_run.v1.json"),
    )

    def _fake_process(self, clip_result, spec):
        output_path = self.output_dir / f"{spec.output_stem}.mp4"
        output_path.write_bytes(b"video")
        return ProcessingResult(
            clip=clip_result.clip,
            output_path=output_path,
            duration=1.0,
            frames_processed=30,
            success=True,
            used_encoder="libx264",
        )

    def _raise_artifact_error(**_kwargs):
        raise OSError("sidecar destination is read-only")

    monkeypatch.setattr(ingest_mod.VideoProcessor, "process_clip_with_spec", _fake_process)
    monkeypatch.setattr(ingest_mod, "emit_clip_artifact", _raise_artifact_error)

    with pytest.raises(OSError, match="sidecar destination is read-only"):
        ingest(
            input_dir,
            output_dir,
            manifest=None,
            options=IngestOptions(dry_run=False),
        )


def test_ingest_dry_run_does_not_emit_clip_artifact_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod, "resolve_adapter", lambda *_args, **_kwargs: _SingleClipAdapter()
    )
    monkeypatch.setattr(ingest_mod.VideoProcessor, "_detect_encoders", lambda _self: [])
    monkeypatch.setattr(
        ingest_mod,
        "emit_ingest_run",
        lambda **_kwargs: ("run-id", output_dir / "cosmos_ingest_run.v1.json"),
    )
    monkeypatch.setattr(
        ingest_mod,
        "emit_clip_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not emit clip artifact provenance")
        ),
    )

    outputs = ingest(
        input_dir,
        output_dir,
        manifest=None,
        options=IngestOptions(dry_run=True),
    )

    assert outputs == [output_dir / "clip1.mp4"]
    plan_path = output_dir / "cosmos_ingest_dry_run.v1.json"
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text())
    assert plan["schema"] == "cosmos-dry-run-plan-v1"
    assert plan["commands"][0]["argv"]


def test_ingest_dry_run_writes_empty_plan_for_no_matching_clips(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod, "resolve_adapter", lambda *_args, **_kwargs: _SingleClipAdapter()
    )
    monkeypatch.setattr(ingest_mod.VideoProcessor, "_detect_encoders", lambda _self: [])

    def _write_run(**_kwargs):
        path = output_dir / "cosmos_ingest_run.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return ("run-id", path)

    monkeypatch.setattr(ingest_mod, "emit_ingest_run", _write_run)

    outputs = ingest(
        input_dir,
        output_dir,
        manifest=None,
        options=IngestOptions(dry_run=True, clips=["MISSING"]),
    )

    assert outputs == []
    assert (output_dir / "cosmos_ingest_run.v1.json").exists()
    plan_path = output_dir / "cosmos_ingest_dry_run.v1.json"
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text())
    assert plan["schema"] == "cosmos-dry-run-plan-v1"
    assert plan["outputs"] == []
    assert plan["commands"] == []
    assert plan["validation"][0]["message"] == "No clips matched discovery/filter criteria."


def test_ingest_dry_run_persists_temp_manifest_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ingest_mod = importlib.import_module("cosmos.sdk.ingest")
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingest_mod, "resolve_adapter", lambda *_args, **_kwargs: _TempManifestAdapter()
    )
    monkeypatch.setattr(ingest_mod.VideoProcessor, "_detect_encoders", lambda _self: [])

    def _write_run(**_kwargs):
        path = output_dir / "cosmos_ingest_run.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return ("run-id", path)

    monkeypatch.setattr(ingest_mod, "emit_ingest_run", _write_run)

    outputs = ingest(
        input_dir,
        output_dir,
        manifest=None,
        options=IngestOptions(dry_run=True),
    )

    assert outputs == [output_dir / "clip1.mp4"]
    assert not (output_dir / "adapter-concat.txt").exists()
    plan = json.loads((output_dir / "cosmos_ingest_dry_run.v1.json").read_text())
    argv = plan["commands"][0]["argv"]
    assert str(output_dir / "adapter-concat.txt") not in argv
    persisted = output_dir / ".cosmos-dry-run" / "ingest" / "CLIP1-00.txt"
    assert persisted.exists()
    assert str(persisted) in argv
    assert any(item["path"] == str(persisted) for item in plan["inputs"])
    assert str(persisted) in plan["side_effects"]["writes_metadata"]


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
