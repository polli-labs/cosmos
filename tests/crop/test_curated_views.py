import json
import logging
from pathlib import Path

import pytest
from cosmos.crop.curated_views import parse_curated_views
from cosmos.sdk.crop import RectCropJob

SAMPLE_VIEW = {
    "id": "CLIP18_test_view",
    "source": {"clip": "CLIP18", "date": "2025-04-25"},
    "trim": {"start_s": 0, "end_s": 20},
    "crop_norm": {"x0": 0.0, "y0": 0.417, "w": 0.399, "h": 0.353},
    "annotations": {"pollinators": ["Southern dogface"], "plants": ["sage"]},
    "preprocess": {},
}


def _write_spec(tmp_path: Path, views: list) -> Path:
    spec = {"schema": "polli-curated-view-spec-v1", "views": views}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


def _create_source(
    source_root: Path, date_fs: str, clip: str, pattern: str = "{date}/8k/{clip}.mp4"
) -> Path:
    rel = pattern.format(date=date_fs, clip=clip)
    p = source_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake_video")
    return p


def test_parse_curated_views_basic(tmp_path: Path) -> None:
    """Parse a spec with a single view and mock filesystem."""
    source_root = tmp_path / "data"
    _create_source(source_root, "Apr25", "CLIP18")
    spec_path = _write_spec(tmp_path, [SAMPLE_VIEW])

    result = parse_curated_views(spec_path, source_root)
    assert len(result) == 1
    src, job = result[0]
    assert src.exists()
    assert src.name == "CLIP18.mp4"
    assert isinstance(job, RectCropJob)
    assert job.view_id == "CLIP18_test_view"
    assert job.x0 == pytest.approx(0.0)
    assert job.w == pytest.approx(0.399)
    assert job.start == 0
    assert job.end == 20
    assert job.normalized is True


def test_parse_curated_views_missing_source(tmp_path: Path) -> None:
    """Missing source file raises FileNotFoundError."""
    source_root = tmp_path / "data"
    source_root.mkdir(parents=True)
    # Don't create the source file
    spec_path = _write_spec(tmp_path, [SAMPLE_VIEW])

    with pytest.raises(FileNotFoundError, match="CLIP18"):
        parse_curated_views(spec_path, source_root)


def test_parse_curated_views_custom_pattern(tmp_path: Path) -> None:
    """Custom clip_pattern is used for path resolution."""
    source_root = tmp_path / "data"
    custom_pattern = "raw/{date}/{clip}.mp4"
    _create_source(source_root, "Apr25", "CLIP18", pattern=custom_pattern)
    spec_path = _write_spec(tmp_path, [SAMPLE_VIEW])

    result = parse_curated_views(spec_path, source_root, clip_pattern=custom_pattern)
    assert len(result) == 1
    assert result[0][0].exists()


def test_parse_curated_views_annotations_carried(tmp_path: Path) -> None:
    """Annotations from the spec are carried through to the RectCropJob."""
    source_root = tmp_path / "data"
    _create_source(source_root, "Apr25", "CLIP18")
    spec_path = _write_spec(tmp_path, [SAMPLE_VIEW])

    result = parse_curated_views(spec_path, source_root)
    job = result[0][1]
    assert job.annotations == {"pollinators": ["Southern dogface"], "plants": ["sage"]}


def test_parse_curated_views_color_correction_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Views with color_correction log a warning."""
    source_root = tmp_path / "data"
    _create_source(source_root, "Apr25", "CLIP18")
    view = {
        **SAMPLE_VIEW,
        "id": "CLIP18_cc_test",
        "preprocess": {"color_correction": "Needs correction"},
    }
    spec_path = _write_spec(tmp_path, [view])

    with caplog.at_level(logging.WARNING, logger="cosmos.crop.curated_views"):
        result = parse_curated_views(spec_path, source_root)

    assert len(result) == 1
    assert any("color_correction" in rec.message for rec in caplog.records)
    assert any("not yet implemented" in rec.message for rec in caplog.records)


def test_parse_curated_views_multiple_dates(tmp_path: Path) -> None:
    """Views spanning different dates resolve to correct filesystem paths."""
    source_root = tmp_path / "data"
    _create_source(source_root, "Apr25", "CLIP18")
    _create_source(source_root, "Apr28", "CLIP17")

    views = [
        SAMPLE_VIEW,
        {
            "id": "CLIP17_test",
            "source": {"clip": "CLIP17", "date": "2025-04-28"},
            "trim": {"start_s": 0, "end_s": 15},
            "crop_norm": {"x0": 0.1, "y0": 0.2, "w": 0.3, "h": 0.4},
            "annotations": {},
            "preprocess": {},
        },
    ]
    spec_path = _write_spec(tmp_path, views)

    result = parse_curated_views(spec_path, source_root)
    assert len(result) == 2
    assert "Apr25" in str(result[0][0])
    assert "Apr28" in str(result[1][0])
