import glob
import os
from pathlib import Path

import pytest
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.crop import crop


def _pick_input_video() -> Path:
    # Choose first MP4 under known cosmos outputs
    bases = [
        "dev/fixtures/cache/outputs/batch0_full_9.5k_18crf",
        "/Users/carbon/Data/clients/ladybird/batch_0/cosmos_output_1080p",
        "/Users/carbon/Data/clients/ladybird/batch_0/cosmos_output",
        "/Users/carbon/Data/clients/ladybird/batch_0/cosmos_output_standalone",
        "/Users/carbon/Data/clients/ladybird/batch_0/cosmos_output_4k_highest",
    ]
    for b in bases:
        vids = glob.glob(f"{b}/**/*.mp4", recursive=True)
        if vids:
            return Path(vids[0])
    raise FileNotFoundError("No cosmos output mp4 found under ladybird")


def _pick_jobs_file() -> Path:
    files = glob.glob("/Users/carbon/Data/clients/ladybird/cropped/**/job_settings.json", recursive=True)
    if not files:
        raise FileNotFoundError("No squarecrop job_settings.json found under ladybird/cropped")
    return Path(files[0])


@pytest.mark.localdata
def test_ladybird_squarecrop_jobs_dryrun(tmp_path: Path) -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests")
    video = _pick_input_video()
    jobs_path = _pick_jobs_file()
    jobs = parse_jobs_json(jobs_path)
    out_dir = tmp_path / "crop"
    out = crop([video], jobs, out_dir, ffmpeg_opts={"dry_run": True})
    assert out and out[0].exists()
