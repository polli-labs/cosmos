from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cosmos.sdk.ingest import IngestOptions, ingest

_DEFAULT_FIXTURES_DIR = "dev/fixtures/cache"
_TARGET_WIDTH = 7680
_TARGET_HEIGHT = 4320
_ALLOWED_ENCODERS = ("h264_videotoolbox", "h264_nvenc", "h264_qsv", "h264_amf", "libx264")


def _require_8k_repro_opt_in() -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    if os.environ.get("COSMOS_RUN_8K_REPRO") != "1":
        pytest.skip("Set COSMOS_RUN_8K_REPRO=1 to run 8K ingest reproduction")
    if os.environ.get("CI") and os.environ.get("COSMOS_RUN_8K_IN_CI") != "1":
        pytest.skip("8K reproduction is disabled in CI unless COSMOS_RUN_8K_IN_CI=1")


def _require_fixtures() -> tuple[Path, Path]:
    fixtures_root = Path(os.environ.get("COSMOS_FIXTURES_DIR", _DEFAULT_FIXTURES_DIR))
    input_dir = fixtures_root / "raw"
    manifest = fixtures_root / "LADYBIRD.xml"
    if not input_dir.exists():
        pytest.skip(
            f"Missing raw fixture directory at {input_dir}. Run `make fixtures.download fixtures.unpack`."
        )
    if not manifest.exists():
        pytest.skip(f"Missing manifest at {manifest}. Run `make fixtures.download`.")
    return input_dir, manifest


def _clips_from_env() -> list[str]:
    raw = os.environ.get("COSMOS_8K_CLIPS", "CLIP1")
    clips = [token.strip() for token in raw.replace(",", " ").split() if token.strip()]
    return clips or ["CLIP1"]


@pytest.mark.localdata
def test_ladybird_ingest_reproduce_8k_windowed(tmp_path: Path) -> None:
    _require_8k_repro_opt_in()
    input_dir, manifest = _require_fixtures()

    window_seconds = float(os.environ.get("COSMOS_8K_WINDOW_SECONDS", "2.0"))
    clips = _clips_from_env()
    out_dir = tmp_path / "out_8k"

    options = IngestOptions(
        width=_TARGET_WIDTH,
        height=_TARGET_HEIGHT,
        quality_mode=os.environ.get("COSMOS_8K_QUALITY_MODE", "balanced"),
        dry_run=False,
        window_seconds=window_seconds,
        scale_filter=os.environ.get("COSMOS_8K_SCALE_FILTER", "bicubic"),
        clips=clips,
    )
    outputs = ingest(input_dir, out_dir, manifest=manifest, options=options)

    assert outputs, "no outputs produced"
    run_artifact = out_dir / "cosmos_ingest_run.v1.json"
    assert run_artifact.exists(), "missing run-level provenance"
    run_payload = json.loads(run_artifact.read_text())
    assert run_payload["options"]["resolution"] == [_TARGET_WIDTH, _TARGET_HEIGHT]
    assert run_payload["options"]["window_seconds"] == window_seconds

    for output_path in outputs:
        assert output_path.exists(), f"missing output {output_path}"
        assert output_path.stat().st_size > 0, f"empty output {output_path}"

        cmd_path = output_path.with_suffix(output_path.suffix + ".cmd.txt")
        assert cmd_path.exists(), f"missing command log for {output_path}"
        cmdline = cmd_path.read_text()
        assert f"scale={_TARGET_WIDTH}:{_TARGET_HEIGHT}" in cmdline
        assert any(encoder in cmdline for encoder in _ALLOWED_ENCODERS)

        clip_artifact = output_path.with_suffix(output_path.suffix + ".cosmos_clip.v1.json")
        assert clip_artifact.exists(), f"missing clip provenance for {output_path}"
        clip_payload = json.loads(clip_artifact.read_text())
        assert clip_payload["output"]["sha256"]
        assert clip_payload["video"]["width"] == _TARGET_WIDTH
        assert clip_payload["video"]["height"] == _TARGET_HEIGHT
