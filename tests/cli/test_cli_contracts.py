from __future__ import annotations

import json
from pathlib import Path

from cosmos.cli.cosmos_app import app
from cosmos.preview.pipeline import PreviewRunResult
from typer.testing import CliRunner

runner = CliRunner()


def test_root_help_exposes_process_and_hides_pipeline() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "process" in result.stdout
    assert "pipeline" not in result.stdout


def test_ingest_json_output_contract(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(
        "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "cosmos.cli.ingest_cli.ingest",
        lambda *_args, **_kwargs: [output_dir / "clip_a.mp4"],
    )

    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--yes",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos ingest run"
    assert payload["count"] == 1
    assert payload["outputs"] == [str(output_dir / "clip_a.mp4")]
    assert "error:" not in result.output.lower()


def test_ingest_runtime_maps_to_ffmpeg_error_exit_code(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(
        "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
        lambda **_kwargs: None,
    )

    def _raise_ffmpeg(*_args, **_kwargs):
        raise RuntimeError("ffmpeg not found")

    monkeypatch.setattr("cosmos.cli.ingest_cli.ingest", _raise_ffmpeg)

    result = runner.invoke(
        app,
        [
            "ingest",
            "run",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--yes",
        ],
    )
    assert result.exit_code == 4
    assert "ffmpeg not found" in result.output


def test_crop_run_non_interactive_requires_out_dir(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"fake")

    result = runner.invoke(
        app,
        [
            "crop",
            "run",
            "--input",
            str(video),
            "--no-input",
        ],
    )
    assert result.exit_code == 2
    assert "Output directory is required" in result.stderr


def test_curated_views_json_output_contract(monkeypatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_clip = source_root / "Apr25" / "8k" / "CLIP18.mp4"
    source_clip.parent.mkdir(parents=True, exist_ok=True)
    source_clip.write_bytes(b"fake")

    spec = tmp_path / "views.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "polli-curated-view-spec-v1",
                "views": [
                    {
                        "id": "view_1",
                        "source": {"clip": "CLIP18", "date": "2025-04-25"},
                        "crop_norm": {"x0": 0.0, "y0": 0.2, "w": 0.4, "h": 0.4},
                        "trim": {"start_s": 0, "end_s": 2},
                    }
                ],
            }
        )
    )
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "cosmos.cli.crop_cli.crop",
        lambda *_args, **_kwargs: [out_dir / "view_1.mp4"],
    )

    result = runner.invoke(
        app,
        [
            "crop",
            "curated-views",
            "--spec",
            str(spec),
            "--source-root",
            str(source_root),
            "--out",
            str(out_dir),
            "--yes",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos crop curated-views"
    assert payload["count"] == 1
    assert payload["outputs"] == [str(out_dir / "view_1.mp4")]


def test_crop_preview_json_output_contract(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    video.write_bytes(b"fake")
    out_dir = tmp_path / "preview_out"

    monkeypatch.setattr(
        "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "cosmos.cli.crop_cli.sdk_preview",
        lambda *_args, **_kwargs: PreviewRunResult(
            run_path=out_dir / "cosmos_crop_preview_run.v1.json",
            clip_plan_paths=[out_dir / "preview_clip_a" / "preview_plan.v1.json"],
            frame_paths=[],
            sheet_paths=[out_dir / "preview_clip_a" / "sheets" / "sheet_frame_start.png"],
            stacked_paths=[out_dir / "preview_clip_a" / "stacked" / "stacked_t_000.000.png"],
        ),
    )

    result = runner.invoke(
        app,
        [
            "crop",
            "preview",
            "--input",
            str(video),
            "--out",
            str(out_dir),
            "--yes",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos crop preview"
    assert payload["run_artifact"] == str(out_dir / "cosmos_crop_preview_run.v1.json")
    assert payload["count"] == 4


def test_curated_views_preview_json_output_contract(monkeypatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_clip = source_root / "Apr25" / "8k" / "CLIP18.mp4"
    source_clip.parent.mkdir(parents=True, exist_ok=True)
    source_clip.write_bytes(b"fake")

    spec = tmp_path / "views.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "polli-curated-view-spec-v1",
                "views": [
                    {
                        "id": "view_1",
                        "source": {"clip": "CLIP18", "date": "2025-04-25"},
                        "crop_norm": {"x0": 0.0, "y0": 0.2, "w": 0.4, "h": 0.4},
                        "trim": {"start_s": 0, "end_s": 2},
                    }
                ],
            }
        )
    )
    out_dir = tmp_path / "preview_out"

    monkeypatch.setattr(
        "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "cosmos.cli.crop_cli.sdk_preview_curated_views",
        lambda *_args, **_kwargs: PreviewRunResult(
            run_path=out_dir / "cosmos_crop_preview_run.v1.json",
            clip_plan_paths=[out_dir / "preview_clip_a" / "preview_plan.v1.json"],
            frame_paths=[],
            sheet_paths=[out_dir / "preview_clip_a" / "sheets" / "sheet_frame_start.png"],
            stacked_paths=[out_dir / "preview_clip_a" / "stacked" / "stacked_t_000.000.png"],
        ),
    )

    result = runner.invoke(
        app,
        [
            "crop",
            "curated-views-preview",
            "--spec",
            str(spec),
            "--source-root",
            str(source_root),
            "--out",
            str(out_dir),
            "--yes",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos crop curated-views-preview"
    assert payload["run_artifact"] == str(out_dir / "cosmos_crop_preview_run.v1.json")
    assert payload["count"] == 4


def test_pipeline_alias_warns_and_processes(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(
        "cosmos.cli.cosmos_app.sdk_ingest",
        lambda *_args, **_kwargs: [output_dir / "clip.mp4"],
    )

    result = runner.invoke(
        app,
        ["pipeline", str(input_dir), str(output_dir), "--dry-run", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "cosmos process"
    assert payload["ingest_count"] == 1
    assert "deprecated" in result.output
