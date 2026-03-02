"""Integration tests for determinism profiles through CLI and SDK layers."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from cosmos.cli.cosmos_app import app
from cosmos.sdk.crop import CropJob, crop
from cosmos.sdk.optimize import OptimizeOptions, optimize
from typer.testing import CliRunner

optimize_mod = importlib.import_module("cosmos.sdk.optimize")
crop_mod = importlib.import_module("cosmos.sdk.crop")
runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI: --profile flag visible and accepted
# ---------------------------------------------------------------------------


class TestProfileCLIFlags:
    def test_optimize_help_shows_profile_flag(self) -> None:
        result = runner.invoke(app, ["optimize", "run", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.stdout

    def test_ingest_help_shows_profile_flag(self) -> None:
        result = runner.invoke(app, ["ingest", "run", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.stdout

    def test_crop_help_shows_profile_flag(self) -> None:
        result = runner.invoke(app, ["crop", "run", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.stdout

    def test_process_help_shows_profile_flag(self) -> None:
        result = runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.stdout


# ---------------------------------------------------------------------------
# CLI: --profile passes through to SDK
# ---------------------------------------------------------------------------


class TestProfileCLIPassthrough:
    def test_optimize_profile_passed_to_sdk(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"fake")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(
            "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
            lambda **_kwargs: None,
        )

        captured_opts: list[OptimizeOptions] = []

        def _capture(*_args, **kwargs):
            captured_opts.append(kwargs.get("options"))
            return [out_dir / "clip_optimized.mp4"]

        monkeypatch.setattr("cosmos.cli.optimize_cli.optimize", _capture)

        result = runner.invoke(
            app,
            [
                "optimize",
                "run",
                "--input",
                str(video),
                "--out-dir",
                str(out_dir),
                "--yes",
                "--dry-run",
                "--json",
                "--profile",
                "strict",
            ],
        )
        assert result.exit_code == 0
        assert len(captured_opts) == 1
        assert captured_opts[0].profile == "strict"

    def test_ingest_profile_passed_to_sdk(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        input_dir.mkdir()
        output_dir.mkdir()

        monkeypatch.setattr(
            "cosmos.ffmpeg.detect.prompt_bootstrap_if_needed",
            lambda **_kwargs: None,
        )

        captured_opts: list[object] = []

        def _capture(*_args, **kwargs):
            captured_opts.append(kwargs.get("options"))
            return [output_dir / "clip.mp4"]

        monkeypatch.setattr("cosmos.cli.ingest_cli.ingest", _capture)

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
                "--profile",
                "strict",
            ],
        )
        assert result.exit_code == 0
        assert len(captured_opts) == 1
        assert captured_opts[0].profile == "strict"


# ---------------------------------------------------------------------------
# SDK: optimize with profile resolves encoder/threads/bitexact
# ---------------------------------------------------------------------------


class TestOptimizeProfileSDK:
    def test_strict_profile_pins_libx264_in_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = tmp_path / "clip.mp4"
        src.write_bytes(b"source")
        out_dir = tmp_path / "out"
        monkeypatch.setattr(optimize_mod, "ensure_ffmpeg_available", lambda: None)

        optimize(
            [src],
            out_dir,
            options=OptimizeOptions(
                mode="transcode",
                dry_run=True,
                profile="strict",
            ),
        )

        plan_path = out_dir / "cosmos_optimize_dry_run.json"
        payload = json.loads(plan_path.read_text())
        cmd = " ".join(payload["planned"][0]["command"])
        assert "-c:v libx264" in cmd
        assert "-bitexact" in cmd

    def test_no_profile_omits_bitexact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = tmp_path / "clip.mp4"
        src.write_bytes(b"source")
        out_dir = tmp_path / "out"
        monkeypatch.setattr(optimize_mod, "ensure_ffmpeg_available", lambda: None)

        optimize(
            [src],
            out_dir,
            options=OptimizeOptions(mode="remux", dry_run=True),
        )

        plan_path = out_dir / "cosmos_optimize_dry_run.json"
        payload = json.loads(plan_path.read_text())
        cmd = " ".join(payload["planned"][0]["command"])
        assert "-bitexact" not in cmd


# ---------------------------------------------------------------------------
# SDK: crop with profile resolves encoder/threads/bitexact
# ---------------------------------------------------------------------------


class TestCropProfileSDK:
    def test_strict_profile_passes_encoder_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        jobs = [CropJob(offset_x=0.0, size=128)]

        captured_kwargs: list[dict] = []

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
            captured_kwargs.append(
                {
                    "encoder_override": encoder_override,
                    "threads": threads,
                    "bitexact": bitexact,
                }
            )
            out.write_bytes(b"out")
            from cosmos.crop.squarecrop import CropRunResult

            return CropRunResult(
                args=["ffmpeg"], encoder_used="libx264", encoder_attempted="libx264"
            )

        monkeypatch.setattr(crop_mod, "run_square_crop", fake_run_square_crop)

        out_dir = tmp_path / "out"
        crop(
            [video],
            jobs,
            out_dir,
            ffmpeg_opts={"dry_run": False, "profile": "strict"},
        )

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["encoder_override"] == "libx264"
        assert captured_kwargs[0]["threads"] == 4
        assert captured_kwargs[0]["bitexact"] is True

    def test_no_profile_leaves_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        jobs = [CropJob(offset_x=0.0, size=128)]

        captured_kwargs: list[dict] = []

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
            captured_kwargs.append(
                {
                    "encoder_override": encoder_override,
                    "threads": threads,
                    "bitexact": bitexact,
                }
            )
            out.write_bytes(b"out")
            from cosmos.crop.squarecrop import CropRunResult

            return CropRunResult(
                args=["ffmpeg"], encoder_used="libx264", encoder_attempted="libx264"
            )

        monkeypatch.setattr(crop_mod, "run_square_crop", fake_run_square_crop)

        out_dir = tmp_path / "out"
        crop([video], jobs, out_dir, ffmpeg_opts={"dry_run": False})

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["encoder_override"] is None
        assert captured_kwargs[0]["threads"] is None
        assert captured_kwargs[0]["bitexact"] is False
