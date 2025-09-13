from pathlib import Path

from cosmos.sdk import CropJob, IngestOptions
from cosmos.sdk import crop as crop_fn
from cosmos.sdk import ingest as ingest_fn


def test_sdk_smoke(tmp_path: Path) -> None:
    # Create a fake input video path to satisfy placeholder logic
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    fake = src_dir / "a.mp4"
    fake.write_bytes(b"")

    out_dir = tmp_path / "out"
    out = ingest_fn(src_dir, out_dir, manifest=None, options=IngestOptions())
    assert isinstance(out, list)  # noqa: S101

    cropped = crop_fn(out, [CropJob()], tmp_path / "crop", ffmpeg_opts={"dry_run": True})
    assert isinstance(cropped, list)  # noqa: S101
