import hashlib
import json
import os
from pathlib import Path

import pytest
from cosmos.sdk.ingest import IngestOptions, ingest


def sha256sum(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            total += len(chunk)
    return total, h.hexdigest()


def _load_expected() -> dict:
    p = Path("dev/fixtures/expected/ladybird_ingest_v1.json")
    return json.loads(p.read_text())


@pytest.mark.localdata
def test_ladybird_known_good_outputs_match_manifest() -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    exp = _load_expected()["outputs"]
    cache_dir = (
        Path(os.environ.get("COSMOS_FIXTURES_DIR", "dev/fixtures/cache"))
        / "outputs/batch0_full_9.5k_18crf"
    )
    good_dir = (
        cache_dir
        if cache_dir.exists()
        else Path("/Users/carbon/Data/clients/ladybird/batch_0/batch0_full_9.5k_18crf")
    )
    if not good_dir.exists():
        pytest.skip("Known-good outputs not present locally or in cache; skip")
    for name, meta in exp.items():
        p = good_dir / name
        assert p.exists(), f"missing {p}"
        size, digest = sha256sum(p)
        assert size == meta["size"]
        assert digest == meta["sha256"]


@pytest.mark.localdata
def test_ladybird_ingest_reproduce(tmp_path: Path) -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    if os.environ.get("COSMOS_RUN_INGEST") != "1":
        pytest.skip("Set COSMOS_RUN_INGEST=1 to run heavy ingest reproduction")

    cache = Path(os.environ.get("COSMOS_FIXTURES_DIR", "dev/fixtures/cache"))
    default_input = Path("/Users/carbon/Data/clients/ladybird/batch_0/raw")
    input_dir = cache / "raw" if (cache / "raw").exists() else default_input
    if not input_dir.exists():
        pytest.skip("No input_dir present in cache or default path; ensure fixtures are downloaded")
    out_dir = tmp_path / "out"
    # Slim reproduction: 4K balanced, 10s window, bicubic scaler, limit filter threads
    opts = IngestOptions(
        width=3840,
        height=2160,
        quality_mode="balanced",
        dry_run=False,
        window_seconds=10.0,
        scale_filter="bicubic",
        filter_threads=2,
        filter_complex_threads=2,
    )
    manifest = (cache / "LADYBIRD.xml") if (cache / "LADYBIRD.xml").exists() else None
    outputs = ingest(input_dir, out_dir, manifest=manifest, options=opts)

    # Slim run: verify outputs exist and encoder/scale flags via command logs
    assert outputs, "no outputs produced"
    for p in outputs:
        cmd = p.with_suffix(p.suffix + ".cmd.txt")
        assert cmd.exists(), f"missing cmd log for {p}"
        cmdline = cmd.read_text()
        assert any(
            enc in cmdline
            for enc in ["h264_videotoolbox", "h264_nvenc", "h264_qsv", "h264_amf", "libx264"]
        )
        assert ":flags=bicubic" in cmdline
