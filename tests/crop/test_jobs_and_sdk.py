import json
import shutil
from pathlib import Path

import pytest
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.crop import CropJob, RectCropJob, crop

ffmpeg_missing = shutil.which("ffmpeg") is None


def test_parse_jobs_rejects_out_of_range_offset(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text('[{"targets":[1080],"offset_x":1.5}]')
    with pytest.raises(ValueError):
        parse_jobs_json(jobs_file)


def test_parse_jobs_rejects_non_positive_targets(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text('[{"targets":[1080,0,-1]}]')
    with pytest.raises(ValueError, match="square target size must be positive"):
        parse_jobs_json(jobs_file)


def test_parse_jobs_rejects_non_positive_size(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text('[{"size":0}]')
    with pytest.raises(ValueError, match="square target size must be positive"):
        parse_jobs_json(jobs_file)


def test_crop_rejects_empty_inputs_without_creating_out_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="At least one input video is required"):
        crop([], [CropJob(size=128)], out_dir, ffmpeg_opts={"dry_run": True})
    assert not out_dir.exists()


def test_crop_rejects_missing_input_in_dry_run_without_creating_out_dir(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    out_dir = tmp_path / "out"
    with pytest.raises(FileNotFoundError, match="Input video does not exist"):
        crop([missing], [CropJob(size=128)], out_dir, ffmpeg_opts={"dry_run": True})
    assert not out_dir.exists()


def test_crop_rejects_directory_input_without_creating_out_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "input-dir"
    input_dir.mkdir()
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="regular file"):
        crop([input_dir], [CropJob(size=128)], out_dir, ffmpeg_opts={"dry_run": True})
    assert not out_dir.exists()


def test_crop_rejects_non_positive_square_size_without_creating_out_dir(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"data")
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="size must be > 0"):
        crop([video], [CropJob(size=0)], out_dir, ffmpeg_opts={"dry_run": True})
    assert not out_dir.exists()


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
    assert all(not p.exists() for p in outputs)
    assert (out_dir / "cosmos_crop_run.v1.json").exists()
    plan = json.loads((out_dir / "cosmos_crop_dry_run.json").read_text())
    assert plan["schema"] == "cosmos-dry-run-plan-v1"
    assert len(plan["commands"]) == 2
    # Filenames include job and size markers for traceability
    assert any("s512" in p.name for p in outputs)
    assert any("s256" in p.name for p in outputs)


def test_square_dry_run_returns_planned_outputs_for_existing_files(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"data")
    out_dir = tmp_path / "out"
    outputs = crop([video], [CropJob(size=128)], out_dir, ffmpeg_opts={"dry_run": True})
    assert len(outputs) == 1
    assert outputs[0] == out_dir / "crop_000_job00_t00_s128.mp4"
    assert not outputs[0].exists()
    plan = json.loads((out_dir / "cosmos_crop_dry_run.json").read_text())
    assert plan["outputs"][0]["path"] == str(outputs[0])
    assert plan["outputs"][0]["will_create_on_apply"] is True


def test_multi_input_multi_job_writes_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    videos = []
    for i in range(2):
        p = tmp_path / f"in{i}.mp4"
        p.write_bytes(b"x" * (i + 1))
        videos.append(p)
    jobs = [CropJob(offset_x=0.0, size=128), CropJob(center_x=0.3, center_y=0.7, size=64)]

    calls: list[str] = []

    def fake_run_square_crop(
        _src,
        out,
        spec,
        dry_run=False,
        prefer_hevc_hw=False,
        encoder_override=None,
        threads=None,
        bitexact=False,
    ):
        out.write_bytes(b"out")
        assert prefer_hevc_hw is False
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


def test_square_crop_real_run_fails_when_view_provenance_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")
    jobs = [CropJob(offset_x=0.0, size=128)]

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(
        crop_mod,
        "emit_crop_run",
        lambda **_kwargs: ("crop-run-id", tmp_path / "cosmos_crop_run.v1.json"),
    )

    def fake_run_square_crop(
        _src,
        out,
        spec,
        dry_run=False,
        prefer_hevc_hw=False,
        encoder_override=None,
        threads=None,
        bitexact=False,
    ):
        out.write_bytes(b"out")
        from cosmos.crop.squarecrop import CropRunResult

        return CropRunResult(args=["ffmpeg"], encoder_used="libx264", encoder_attempted="libx264")

    def _raise_view_error(**_kwargs):
        raise OSError("view sidecar write failed")

    monkeypatch.setattr(crop_mod, "run_square_crop", fake_run_square_crop)
    monkeypatch.setattr(crop_mod, "emit_crop_view", _raise_view_error)

    with pytest.raises(OSError, match="view sidecar write failed"):
        crop([video], jobs, tmp_path / "out", ffmpeg_opts={"dry_run": False})


def test_square_crop_dry_run_does_not_emit_view_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(
        crop_mod,
        "emit_crop_view",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not emit crop view provenance")
        ),
    )

    outputs = crop(
        [video],
        [CropJob(offset_x=0.0, size=128)],
        tmp_path / "out",
        ffmpeg_opts={"dry_run": True},
    )

    assert len(outputs) == 1


def test_rect_crop_real_run_fails_when_view_provenance_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")
    jobs = [RectCropJob(x0=0.1, y0=0.1, w=0.5, h=0.5, view_id="view-a")]

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(
        crop_mod,
        "emit_crop_run",
        lambda **_kwargs: ("crop-run-id", tmp_path / "cosmos_crop_run.v1.json"),
    )
    monkeypatch.setattr("cosmos.ffmpeg.detect._probe_dimensions", lambda _src: (1920, 1080))

    def fake_run_rect_crop(
        _src,
        out,
        spec,
        dry_run=False,
        prefer_hevc_hw=False,
        encoder_override=None,
        threads=None,
        bitexact=False,
    ):
        out.write_bytes(b"out")
        from cosmos.crop.squarecrop import CropRunResult

        return CropRunResult(args=["ffmpeg"], encoder_used="libx264", encoder_attempted="libx264")

    def _raise_view_error(**_kwargs):
        raise OSError("rect view sidecar write failed")

    monkeypatch.setattr(crop_mod, "run_rect_crop", fake_run_rect_crop)
    monkeypatch.setattr(crop_mod, "emit_crop_view", _raise_view_error)

    with pytest.raises(OSError, match="rect view sidecar write failed"):
        crop([video], jobs, tmp_path / "out", ffmpeg_opts={"dry_run": False})


def test_rect_crop_dry_run_does_not_emit_view_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(
        crop_mod,
        "emit_crop_view",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not emit crop view provenance")
        ),
    )

    def fake_run_rect_crop(
        _src,
        out,
        spec,
        dry_run=False,
        prefer_hevc_hw=False,
        encoder_override=None,
        threads=None,
        bitexact=False,
    ):
        from cosmos.crop.squarecrop import CropRunResult

        return CropRunResult(args=["ffmpeg"], encoder_used="libx264", encoder_attempted="libx264")

    monkeypatch.setattr(crop_mod, "run_rect_crop", fake_run_rect_crop)

    outputs = crop(
        [video],
        [RectCropJob(x0=0.1, y0=0.1, w=0.5, h=0.5, view_id="view-a")],
        tmp_path / "out",
        ffmpeg_opts={"dry_run": True},
    )

    assert len(outputs) == 1


def test_prefer_hevc_flag_passes_to_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")
    jobs = [CropJob(offset_x=0.0, size=128)]

    seen_prefer_hevc: list[bool] = []

    def fake_run_square_crop(
        _src,
        out,
        spec,
        dry_run=False,
        prefer_hevc_hw=False,
        encoder_override=None,
        threads=None,
        bitexact=False,
    ):
        out.write_bytes(b"out")
        seen_prefer_hevc.append(prefer_hevc_hw)
        from cosmos.crop.squarecrop import CropRunResult

        return CropRunResult(
            args=["ffmpeg"], encoder_used="hevc_videotoolbox", encoder_attempted="hevc_videotoolbox"
        )

    import importlib

    crop_mod = importlib.import_module("cosmos.sdk.crop")
    monkeypatch.setattr(crop_mod, "run_square_crop", fake_run_square_crop)
    out_dir = tmp_path / "out"
    outputs = crop([video], jobs, out_dir, ffmpeg_opts={"dry_run": False, "prefer_hevc_hw": True})
    assert len(outputs) == 1
    assert seen_prefer_hevc == [True]


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


def test_crop_rejects_mixed_job_types(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"data")
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="all CropJob or all RectCropJob"):
        crop(
            [video],
            [CropJob(size=128), RectCropJob(x0=0.0, y0=0.0, w=0.5, h=0.5)],  # type: ignore[arg-type]
            out_dir,
            ffmpeg_opts={"dry_run": True},
        )


def test_rect_crop_normalized_bounds_validation(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"data")
    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="x0 \\+ w must be <= 1.0"):
        crop(
            [video],
            [RectCropJob(x0=0.8, y0=0.0, w=0.3, h=0.5)],
            out_dir,
            ffmpeg_opts={"dry_run": True},
        )
