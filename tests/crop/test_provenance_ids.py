from pathlib import Path

import pytest
from cosmos.sdk import provenance
from cosmos.sdk.provenance import emit_clip_artifact, emit_crop_view


def test_deterministic_ids_same_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"abc")
    out.write_bytes(b"def")

    # Stub ffprobe to avoid needing real media
    monkeypatch.setattr(
        provenance,
        "ffprobe_video",
        lambda path: {
            "width": 100,
            "height": 50,
            "width_px": 100,
            "height_px": 50,
            "fps": 10.0,
            "duration_sec": 1.0,
        },
    )

    run_id = "ing_123"
    clip_json = emit_clip_artifact(
        ingest_run_id=run_id,
        clip_name="clip",
        output_path=src,
        encode_info={"codec": "libx264"},
        time_ms=None,
        frames=None,
    )
    first = clip_json.read_text()
    # Re-emit view twice to confirm stable ids
    view1 = emit_crop_view(
        crop_run_id="crop_1",
        source_path=src,
        output_path=out,
        crop_spec={"size": 100},
        encode_info={"codec": "libx264"},
        job_ref="job0",
    )
    view2 = emit_crop_view(
        crop_run_id="crop_1",
        source_path=src,
        output_path=out,
        crop_spec={"size": 100},
        encode_info={"codec": "libx264"},
        job_ref="job0",
    )
    assert view1.read_text() == view2.read_text()
    assert "view-" in view1.read_text()
    assert "clip-" in first


def test_ids_change_with_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"abc")
    out.write_bytes(b"def")
    monkeypatch.setattr(
        provenance,
        "ffprobe_video",
        lambda path: {
            "width": 100,
            "height": 50,
            "width_px": 100,
            "height_px": 50,
            "fps": 10.0,
            "duration_sec": 1.0,
        },
    )
    view1 = emit_crop_view(
        crop_run_id="crop_1",
        source_path=src,
        output_path=out,
        crop_spec={"size": 100},
        encode_info={"codec": "libx264"},
        job_ref="job0",
    )
    view1_json = view1.read_text()
    # Change content -> different sha -> different id
    out.write_bytes(b"zzz")
    view2 = emit_crop_view(
        crop_run_id="crop_1",
        source_path=src,
        output_path=out,
        crop_spec={"size": 100},
        encode_info={"codec": "libx264"},
        job_ref="job0",
    )
    assert view1_json != view2.read_text()
