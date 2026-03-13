from __future__ import annotations

import json
from pathlib import Path

import pytest
from cosmos.sdk import provenance
from cosmos.sdk.provenance import emit_optimize_run, emit_optimized_artifact


def test_emit_optimize_run_and_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src.mp4"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"source")
    out.write_bytes(b"output")

    monkeypatch.setattr(
        provenance,
        "ffprobe_video",
        lambda _path: {
            "width": 1920,
            "height": 1080,
            "width_px": 1920,
            "height_px": 1080,
            "fps": 30.0,
            "duration_sec": 2.0,
        },
    )

    run_id, run_path = emit_optimize_run(
        output_dir=tmp_path,
        options={"mode": "auto", "target_height": 1080},
        inputs=[{"path": str(src)}],
    )
    assert run_path.exists()
    run_payload = json.loads(run_path.read_text())
    assert run_payload["optimize_run_id"] == run_id
    assert run_payload["tool"] == "cosmos-optimize"

    artifact = emit_optimized_artifact(
        optimize_run_id=run_id,
        mode="transcode",
        source_path=src,
        output_path=out,
        transform={"mode": "transcode", "target_height": 1080, "fps": 30.0},
        encode_info={"impl": "libx264", "crf": 23},
    )
    assert artifact.exists()
    payload = json.loads(artifact.read_text())
    assert payload["optimize_run_id"] == run_id
    assert payload["mode"] == "transcode"
    assert payload["source"]["sha256"] == provenance.sha256_file(src)
    assert payload["output"]["sha256"] == provenance.sha256_file(out)
