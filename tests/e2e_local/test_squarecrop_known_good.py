import hashlib
import json
import os
from pathlib import Path

import pytest


def sha256sum(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            total += len(chunk)
    return total, h.hexdigest()


def _load_expected() -> dict:
    p = Path("dev/fixtures/expected/squarecrop_v1.json")
    return json.loads(p.read_text())


@pytest.mark.localdata
def test_squarecrop_known_good_hashes() -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    exp = _load_expected()["jobs"]
    base_cache = Path(os.environ.get("COSMOS_FIXTURES_DIR", "dev/fixtures/cache")) / "crop_outputs"
    base_default = Path("/Users/carbon/Data/clients/ladybird/cropped")
    # Try cache first, else fall back to default, else skip
    base = base_cache if base_cache.exists() else base_default
    if not base.exists():
        pytest.skip("No squarecrop outputs available in cache or default path; skip")
    for job, files in exp.items():
        job_dir = base / job
        if not job_dir.exists():
            pytest.skip(f"Job dir missing: {job_dir}")
        for meta in files:
            p = job_dir / meta["file"]
            assert p.exists(), f"missing {p}"
            size, digest = sha256sum(p)
            assert size == meta["size"], f"size mismatch for {p}"
            assert digest == meta["sha256"], f"sha mismatch for {p}"

