import json
import subprocess
from pathlib import Path

import pytest
from cosmos.ingest.manifest import ManifestParser
from cosmos.ingest.validation import (
    InputValidator,
    ValidationLevel,
)


@pytest.fixture
def sample_manifest(tmp_path: Path) -> Path:
    xml = """
<Clip_Manifest NumDirs="2">
  <_1 Name="CLIP1" In="0" InIdx="0" Out="0" OutIdx="100" Locked="True" InStr="07:27:38.022 08/13/2024" Epoch="1723559258.022" Pos="0H/0M/0S/" />
</Clip_Manifest>
"""
    p = tmp_path / "m.xml"
    p.write_text(xml)
    return p


def test_validate_system_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_manifest: Path) -> None:
    parser = ManifestParser(sample_manifest)
    v = InputValidator(tmp_path, tmp_path, parser)
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError
    monkeypatch.setattr(subprocess, "run", fake_run)
    issues = v.validate_system()
    assert any(i.level == ValidationLevel.ERROR and "FFmpeg" in i.message for i in issues)


def test_load_segment_valid(tmp_path: Path, sample_manifest: Path) -> None:
    parser = ManifestParser(sample_manifest)
    v = InputValidator(tmp_path, tmp_path, parser)
    seg = tmp_path / "0H/0M/0S"
    seg.mkdir(parents=True)
    meta = {
        "Time": {"x0": 1000.0, "xi-x0": [0.0, 0.1, 0.2, 0.3]},
    }
    (seg / "meta.json").write_text(json.dumps(meta))
    for i in range(4):
        (seg / f"chunk_{i}.ts").touch()
    info = v.load_segment(seg)
    assert info is not None
    assert info.frame_count == 4


def test_validate_clip_paths(tmp_path: Path, sample_manifest: Path) -> None:
    parser = ManifestParser(sample_manifest)
    v = InputValidator(tmp_path, tmp_path, parser)
    clip = parser.get_clips()[0]
    # No segments present
    result = v.validate_clip(clip)
    assert result.clip.name == "CLIP1"
    assert not result.segments

