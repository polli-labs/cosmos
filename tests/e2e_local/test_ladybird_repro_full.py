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
    return json.loads(Path("dev/fixtures/expected/ladybird_ingest_v1.json").read_text())


@pytest.mark.localdata
def test_ladybird_ingest_reproduce_full(tmp_path: Path) -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    if os.environ.get("COSMOS_FULL_REPRO") != "1":
        pytest.skip("Set COSMOS_FULL_REPRO=1 to run full 9.5k reproduction")

    cache = Path(os.environ.get("COSMOS_FIXTURES_DIR", "dev/fixtures/cache"))
    default_input = Path("/Users/carbon/Data/clients/ladybird/batch_0/raw")
    input_dir = cache / "raw" if (cache / "raw").exists() else default_input
    if not input_dir.exists():
        pytest.skip("No input_dir present in cache or default path; ensure fixtures are downloaded")

    out_dir = tmp_path / "out"
    manifest = (cache / "LADYBIRD.xml") if (cache / "LADYBIRD.xml").exists() else None

    # Full-size reproduction (may take a long time)
    opts = IngestOptions(width=9280, height=6300, quality_mode="quality", crf=18, dry_run=False)
    outputs = ingest(input_dir, out_dir, manifest=manifest, options=opts)

    # Compare against known-good outputs
    exp = _load_expected()["outputs"]
    got = {p.name: sha256sum(p) for p in outputs if p.name in exp}
    for name, meta in exp.items():
        assert name in got, f"missing produced {name}"
        size, digest = got[name]
        assert size == meta["size"], f"size mismatch for {name}"
        assert digest == meta["sha256"], f"sha mismatch for {name}"
