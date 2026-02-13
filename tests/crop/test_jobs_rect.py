import json
from pathlib import Path

import pytest
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.crop import RectCropJob


def test_parse_rect_job_norm(tmp_path: Path) -> None:
    """Parse a rect job with normalized crop_norm coords."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_norm": {"x0": 0.1, "y0": 0.2, "w": 0.3, "h": 0.4},
                    "view_id": "test_view",
                }
            ]
        )
    )
    jobs = parse_jobs_json(jobs_file)
    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, RectCropJob)
    assert job.x0 == pytest.approx(0.1)
    assert job.y0 == pytest.approx(0.2)
    assert job.w == pytest.approx(0.3)
    assert job.h == pytest.approx(0.4)
    assert job.normalized is True
    assert job.view_id == "test_view"


def test_parse_rect_job_pixel_mode(tmp_path: Path) -> None:
    """Parse a rect job with pixel crop_px coords."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_px": {"x0": 100, "y0": 200, "w": 640, "h": 480},
                }
            ]
        )
    )
    jobs = parse_jobs_json(jobs_file)
    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, RectCropJob)
    assert job.x0 == 100.0
    assert job.w == 640.0
    assert job.normalized is False


def test_parse_rect_job_list_format(tmp_path: Path) -> None:
    """crop_norm as a list of 4 floats."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([{"crop_mode": "rect", "crop_norm": [0.1, 0.2, 0.3, 0.4]}]))
    jobs = parse_jobs_json(jobs_file)
    assert len(jobs) == 1
    assert isinstance(jobs[0], RectCropJob)
    assert jobs[0].x0 == pytest.approx(0.1)


def test_parse_rect_job_validation_x_overflow(tmp_path: Path) -> None:
    """x0 + w > 1.0 should raise ValueError."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps([{"crop_mode": "rect", "crop_norm": {"x0": 0.8, "y0": 0.0, "w": 0.5, "h": 0.5}}])
    )
    with pytest.raises(ValueError, match="x0 \\+ w exceeds 1.0"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_validation_y_overflow(tmp_path: Path) -> None:
    """y0 + h > 1.0 should raise ValueError."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps([{"crop_mode": "rect", "crop_norm": {"x0": 0.0, "y0": 0.8, "w": 0.3, "h": 0.5}}])
    )
    with pytest.raises(ValueError, match="y0 \\+ h exceeds 1.0"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_negative_coord(tmp_path: Path) -> None:
    """Negative coords should raise ValueError."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [{"crop_mode": "rect", "crop_norm": {"x0": -0.1, "y0": 0.0, "w": 0.3, "h": 0.4}}]
        )
    )
    with pytest.raises(ValueError, match="non-negative"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_missing_crop(tmp_path: Path) -> None:
    """crop_mode=rect without crop_norm or crop_px raises."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([{"crop_mode": "rect"}]))
    with pytest.raises(ValueError, match="crop_norm or crop_px"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_both_crop_formats_raises(tmp_path: Path) -> None:
    """Providing both crop_norm and crop_px should raise ValueError."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_norm": {"x0": 0.0, "y0": 0.0, "w": 0.5, "h": 0.5},
                    "crop_px": {"x0": 0, "y0": 0, "w": 640, "h": 480},
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="exactly one of crop_norm or crop_px"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_pixel_negative_coord_raises(tmp_path: Path) -> None:
    """Negative pixel coordinates should raise ValueError."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_px": {"x0": -1, "y0": 0, "w": 640, "h": 480},
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="non-negative"):
        parse_jobs_json(jobs_file)


def test_parse_rect_job_with_trim(tmp_path: Path) -> None:
    """Trim values are parsed correctly for rect jobs."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_norm": {"x0": 0.0, "y0": 0.0, "w": 0.5, "h": 0.5},
                    "trim_start": 5.0,
                    "trim_end": 10.0,
                }
            ]
        )
    )
    jobs = parse_jobs_json(jobs_file)
    assert jobs[0].start == 5.0
    assert jobs[0].end == 10.0


def test_parse_rect_job_with_annotations(tmp_path: Path) -> None:
    """Annotations dict is carried through."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "crop_mode": "rect",
                    "crop_norm": {"x0": 0.0, "y0": 0.0, "w": 0.5, "h": 0.5},
                    "annotations": {"pollinators": ["bee"], "plants": ["sage"]},
                }
            ]
        )
    )
    jobs = parse_jobs_json(jobs_file)
    assert jobs[0].annotations == {"pollinators": ["bee"], "plants": ["sage"]}
