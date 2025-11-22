import json
import os
from pathlib import Path

import pytest
from cosmos.sdk.ingest import IngestOptions, ingest


@pytest.mark.localdata
def test_ladybird_ingest_dryrun(tmp_path: Path) -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    cache = Path(os.environ.get("COSMOS_FIXTURES_DIR", "dev/fixtures/cache"))
    default_input = Path("/Users/carbon/Data/clients/ladybird/batch_0/raw")
    input_dir = cache / "raw" if (cache / "raw").exists() else default_input
    if not input_dir.exists():
        pytest.skip("No input_dir present in cache or default path; ensure fixtures are downloaded")
    out_dir = tmp_path / "out"
    manifest = (cache / "LADYBIRD.xml") if (cache / "LADYBIRD.xml").exists() else None
    opts = IngestOptions(dry_run=True, clips=["CLIP1", "CLIP2"])  # limit to known-good clips
    outputs = ingest(input_dir, out_dir, manifest=manifest, options=opts)
    # dry-run should produce planned outputs and a report
    assert len(outputs) >= 1
    report = out_dir / "cosmos_dry_run.json"
    assert report.exists()
    plan = json.loads(report.read_text())
    assert plan.get("tool") == "cosmos-ingest"
    assert isinstance(plan.get("clips"), list)
