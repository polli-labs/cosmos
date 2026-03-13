"""Tests for the ingest adapter contract, resolution, and built-in adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cosmos.ingest.adapter import ClipDescriptor, FfmpegInputSpec, IngestAdapter
from cosmos.ingest.adapters import resolve_adapter
from cosmos.ingest.adapters.cosm import CosmAdapter
from cosmos.ingest.adapters.generic_media import GenericMediaAdapter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST = """<?xml version="1.0"?>
<Clip_Manifest>
    <_1 Name="CLIP1" Epoch="1700000000.0" Pos="0H/0M/3.8S/"
        InIdx="0" OutIdx="100" Lock="1"
        InStr="14:26:40.000 11/14/2023"/>
    <_2 Name="CLIP2" Epoch="1700000060.0" Pos="0H/1M/0.0S/"
        InIdx="100" OutIdx="200" Lock="1"
        InStr="14:27:40.000 11/14/2023"/>
</Clip_Manifest>
"""


@pytest.fixture()
def cosm_dir(tmp_path: Path) -> Path:
    """Create a minimal COSM directory with manifest and segment data."""
    manifest = tmp_path / "manifest.xml"
    manifest.write_text(SAMPLE_MANIFEST)

    # Create segment dirs for CLIP1 (seconds 3..5)
    for sec in range(3, 6):
        seg = tmp_path / f"0H/0M/{sec}S"
        seg.mkdir(parents=True)
        meta = {
            "Time": {
                "x0": 1700000000.0 + sec - 3,
                "xi-x0": [0.0, 0.1, 0.2, 0.3],
            }
        }
        (seg / "meta.json").write_text(json.dumps(meta))
        for i in range(4):
            (seg / f"chunk_{i}.ts").touch()

    return tmp_path


@pytest.fixture()
def generic_dir(tmp_path: Path) -> Path:
    """Create a flat directory with video files."""
    (tmp_path / "video_a.mp4").write_bytes(b"\x00" * 1024)
    (tmp_path / "video_b.mov").write_bytes(b"\x00" * 512)
    (tmp_path / "readme.txt").write_text("not a video")
    return tmp_path


@pytest.fixture()
def empty_dir(tmp_path: Path) -> Path:
    """Empty directory — no adapter should match."""
    return tmp_path


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_cosm_satisfies_protocol(self) -> None:
        assert isinstance(CosmAdapter(), IngestAdapter)

    def test_generic_satisfies_protocol(self) -> None:
        assert isinstance(GenericMediaAdapter(), IngestAdapter)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class TestDetection:
    def test_cosm_detects_xml_manifest(self, cosm_dir: Path) -> None:
        assert CosmAdapter.detect(cosm_dir) is True

    def test_cosm_rejects_generic_dir(self, generic_dir: Path) -> None:
        assert CosmAdapter.detect(generic_dir) is False

    def test_generic_detects_video_files(self, generic_dir: Path) -> None:
        assert GenericMediaAdapter.detect(generic_dir) is True

    def test_generic_rejects_empty_dir(self, empty_dir: Path) -> None:
        assert GenericMediaAdapter.detect(empty_dir) is False


# ---------------------------------------------------------------------------
# Adapter resolution
# ---------------------------------------------------------------------------


class TestResolveAdapter:
    def test_auto_detects_cosm(self, cosm_dir: Path) -> None:
        adapter = resolve_adapter(cosm_dir)
        assert adapter.name == "cosm"

    def test_auto_detects_generic(self, generic_dir: Path) -> None:
        adapter = resolve_adapter(generic_dir)
        assert adapter.name == "generic-media"

    def test_explicit_cosm(self, cosm_dir: Path) -> None:
        adapter = resolve_adapter(cosm_dir, adapter_name="cosm")
        assert adapter.name == "cosm"

    def test_explicit_generic(self, generic_dir: Path) -> None:
        adapter = resolve_adapter(generic_dir, adapter_name="generic-media")
        assert adapter.name == "generic-media"

    def test_unknown_adapter_raises(self, cosm_dir: Path) -> None:
        with pytest.raises(ValueError, match="Unknown adapter"):
            resolve_adapter(cosm_dir, adapter_name="nonexistent")

    def test_empty_dir_raises(self, empty_dir: Path) -> None:
        with pytest.raises(ValueError, match="No adapter could handle"):
            resolve_adapter(empty_dir)


# ---------------------------------------------------------------------------
# COSM adapter
# ---------------------------------------------------------------------------


class TestCosmAdapter:
    def test_discover_clips(self, cosm_dir: Path) -> None:
        adapter = CosmAdapter()
        clips = adapter.discover_clips(cosm_dir)
        assert len(clips) == 2
        names = [c.name for c in clips]
        assert "CLIP1" in names
        assert "CLIP2" in names

    def test_clip_descriptors_have_extra(self, cosm_dir: Path) -> None:
        adapter = CosmAdapter()
        clips = adapter.discover_clips(cosm_dir)
        for clip in clips:
            assert "_clip_info" in clip.extra
            assert "_manifest_path" in clip.extra

    def test_validate_clip(self, cosm_dir: Path) -> None:
        adapter = CosmAdapter()
        clips = adapter.discover_clips(cosm_dir)
        clip1 = next(c for c in clips if c.name == "CLIP1")
        result = adapter.validate_clip(clip1, cosm_dir, cosm_dir / "out")
        assert result.is_valid
        assert len(result.segments) == 3  # seconds 3, 4, 5

    def test_build_ffmpeg_spec(self, cosm_dir: Path) -> None:
        adapter = CosmAdapter()
        clips = adapter.discover_clips(cosm_dir)
        clip1 = next(c for c in clips if c.name == "CLIP1")
        result = adapter.validate_clip(clip1, cosm_dir, cosm_dir / "out")
        spec = adapter.build_ffmpeg_spec(
            clip1,
            result,
            cosm_dir / "out",
            output_resolution=(3840, 2160),
            scale_filter="bicubic",
        )
        assert isinstance(spec, FfmpegInputSpec)
        assert spec.filter_complex is not None
        assert "hstack=2" in spec.filter_complex
        assert "vstack=2" in spec.filter_complex
        assert spec.output_stem == "CLIP1"
        assert "-f" in spec.input_args
        assert "concat" in spec.input_args
        # Temp files should be cleaned up by processor
        assert len(spec.temp_files) == 1


# ---------------------------------------------------------------------------
# Generic media adapter
# ---------------------------------------------------------------------------


class TestGenericMediaAdapter:
    def test_discover_clips(self, generic_dir: Path) -> None:
        adapter = GenericMediaAdapter()
        clips = adapter.discover_clips(generic_dir)
        names = {c.name for c in clips}
        assert "video_a" in names
        assert "video_b" in names
        assert "readme" not in names  # .txt excluded

    def test_validate_clip(self, generic_dir: Path) -> None:
        adapter = GenericMediaAdapter()
        clips = adapter.discover_clips(generic_dir)
        clip_a = next(c for c in clips if c.name == "video_a")
        result = adapter.validate_clip(clip_a, generic_dir, generic_dir / "out")
        assert result.is_valid
        assert len(result.segments) == 1

    def test_validate_missing_source(self, generic_dir: Path) -> None:
        adapter = GenericMediaAdapter()
        ghost = ClipDescriptor(
            name="ghost",
            start_time_sec=0.0,
            extra={"_source_path": generic_dir / "nonexistent.mp4"},
        )
        result = adapter.validate_clip(ghost, generic_dir, generic_dir / "out")
        assert not result.is_valid

    def test_build_ffmpeg_spec(self, generic_dir: Path) -> None:
        adapter = GenericMediaAdapter()
        clips = adapter.discover_clips(generic_dir)
        clip_a = next(c for c in clips if c.name == "video_a")
        result = adapter.validate_clip(clip_a, generic_dir, generic_dir / "out")
        spec = adapter.build_ffmpeg_spec(
            clip_a,
            result,
            generic_dir / "out",
            output_resolution=(1920, 1080),
            scale_filter="lanczos",
        )
        assert isinstance(spec, FfmpegInputSpec)
        assert spec.filter_complex is not None
        assert "scale=1920:1080" in spec.filter_complex
        # No tile stitching
        assert "hstack" not in spec.filter_complex
        assert spec.output_stem == "video_a"
        assert "-i" in spec.input_args
        # No temp files for direct input
        assert len(spec.temp_files) == 0


# ---------------------------------------------------------------------------
# ClipDescriptor
# ---------------------------------------------------------------------------


class TestClipDescriptor:
    def test_defaults(self) -> None:
        clip = ClipDescriptor(name="test", start_time_sec=0.0)
        assert clip.end_time_sec is None
        assert clip.frame_start == 0
        assert clip.frame_end == 0
        assert clip.extra == {}

    def test_extra_roundtrip(self) -> None:
        clip = ClipDescriptor(
            name="test",
            start_time_sec=10.0,
            extra={"key": "value"},
        )
        assert clip.extra["key"] == "value"


# ---------------------------------------------------------------------------
# FfmpegInputSpec
# ---------------------------------------------------------------------------


class TestFfmpegInputSpec:
    def test_defaults(self) -> None:
        spec = FfmpegInputSpec(input_args=["-i", "test.mp4"])
        assert spec.filter_complex is None
        assert spec.output_stem == ""
        assert spec.extra_output_args == []
        assert spec.temp_files == []

    def test_full_spec(self, tmp_path: Path) -> None:
        concat_list = str(tmp_path / "list.txt")
        spec = FfmpegInputSpec(
            input_args=["-f", "concat", "-safe", "0", "-i", concat_list],
            filter_complex="[0:v:0]scale=1920:1080[out]",
            output_stem="clip1",
            extra_output_args=["-movflags", "+faststart"],
            temp_files=[concat_list],
        )
        assert len(spec.input_args) == 6
        assert spec.filter_complex is not None
        assert spec.output_stem == "clip1"
