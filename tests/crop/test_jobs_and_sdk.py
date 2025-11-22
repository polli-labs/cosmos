import shutil
from pathlib import Path

import pytest
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.crop import CropJob, crop

ffmpeg_missing = shutil.which("ffmpeg") is None


def test_parse_jobs_rejects_out_of_range_offset(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text('[{"targets":[1080],"offset_x":1.5}]')
    with pytest.raises(ValueError):
        parse_jobs_json(jobs_file)


def test_crop_runs_all_jobs_and_targets(tmp_path: Path) -> None:
    if ffmpeg_missing:
        pytest.skip("ffmpeg not available")
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")  # dummy input
    jobs = [
        CropJob(offset_x=0.0, offset_y=0.0, size=512),
        CropJob(center_x=0.5, center_y=0.4, size=256),
    ]
    out_dir = tmp_path / "out"
    outputs = crop([video], jobs, out_dir, ffmpeg_opts={"dry_run": True})
    assert len(outputs) == 2
    assert all(p.exists() for p in outputs)
    # Filenames include job and size markers for traceability
    assert any("s512" in p.name for p in outputs)
    assert any("s256" in p.name for p in outputs)


def test_multi_input_multi_job_writes_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    videos = []
    for i in range(2):
        p = tmp_path / f"in{i}.mp4"
        p.write_bytes(b"x" * (i + 1))
        videos.append(p)
    jobs = [CropJob(offset_x=0.0, size=128), CropJob(center_x=0.3, center_y=0.7, size=64)]

    calls: list[str] = []

    def fake_run_square_crop(_src, out, spec, dry_run=False):
        out.write_bytes(b"out")
        calls.append(out.name)
        from cosmos.crop.squarecrop import CropRunResult

        return CropRunResult(
            args=["ffmpeg"], encoder_used="libx264", encoder_attempted="h264_videotoolbox"
        )

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(crop_mod, "run_square_crop", fake_run_square_crop)
    out_dir = tmp_path / "out"
    outputs = crop(videos, jobs, out_dir, ffmpeg_opts={"dry_run": False})
    assert len(outputs) == 4
    assert sorted(calls) == sorted([p.name for p in outputs])


def test_parse_jobs_rejects_centers_and_offsets(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text('[{"targets":[640],"offset_x":0.1,"center_x":0.2}]')
    with pytest.raises(ValueError):
        parse_jobs_json(jobs_file)


def test_trim_window_validation(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"data")
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError):
        crop(
            [video],
            [CropJob(offset_x=0.0, size=128, start=5.0, end=2.0)],
            out_dir,
            ffmpeg_opts={"dry_run": True},
        )
