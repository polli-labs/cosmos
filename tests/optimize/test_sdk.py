from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest
from cosmos.sdk.optimize import OptimizeOptions, optimize

optimize_mod = importlib.import_module("cosmos.sdk.optimize")


@pytest.fixture(autouse=True)
def _mock_ffmpeg_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(optimize_mod, "ensure_ffmpeg_available", lambda: None)


def test_optimize_dry_run_emits_plan_and_run_artifact(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"

    outputs = optimize(
        [src],
        out_dir,
        options=OptimizeOptions(dry_run=True),
    )

    expected_out = out_dir / "clip_optimized.mp4"
    assert outputs == [expected_out]
    assert (out_dir / "cosmos_optimize_run.v1.json").exists()
    plan_path = out_dir / "cosmos_optimize_dry_run.json"
    assert plan_path.exists()
    payload = json.loads(plan_path.read_text())
    assert payload["planned"][0]["mode"] == "remux"
    assert payload["planned"][0]["output"] == str(expected_out)


def test_optimize_auto_selects_transcode_with_transform_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(optimize_mod, "choose_encoder_for_video", lambda _p: ("libx264", "libx264"))

    optimize(
        [src],
        out_dir,
        options=OptimizeOptions(
            dry_run=True,
            target_height=1080,
            fps=30.0,
        ),
    )

    plan_path = out_dir / "cosmos_optimize_dry_run.json"
    payload = json.loads(plan_path.read_text())
    assert payload["planned"][0]["mode"] == "transcode"
    cmd = " ".join(payload["planned"][0]["command"])
    assert "scale=-2:1080:flags=lanczos" in cmd
    assert "fps=30" in cmd


def test_optimize_requires_force_for_existing_outputs(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "clip_optimized.mp4"
    existing.write_bytes(b"already-there")

    with pytest.raises(FileExistsError):
        optimize(
            [src],
            out_dir,
            options=OptimizeOptions(dry_run=True),
        )


def test_optimize_transcode_falls_back_to_x264_when_auto_hw_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    built_encoders: list[str] = []
    commands: list[list[str]] = []

    monkeypatch.setattr(
        optimize_mod, "choose_encoder_for_video", lambda _p: ("h264_nvenc", "h264_nvenc")
    )

    def _fake_build(
        input_path: Path,
        output_path: Path,
        *,
        encoder: str,
        target_height: int | None,
        fps: float | None,
        crf: int | None,
        faststart: bool,
        threads: int | None = None,
        bitexact: bool = False,
    ) -> list[str]:
        _ = (input_path, output_path, target_height, fps, crf, faststart, threads, bitexact)
        built_encoders.append(encoder)
        return ["ffmpeg", encoder]

    monkeypatch.setattr(optimize_mod, "build_optimize_transcode_args", _fake_build)
    monkeypatch.setattr(
        optimize_mod,
        "emit_optimize_run",
        lambda **_kwargs: ("opt_run", out_dir / "cosmos_optimize_run.v1.json"),
    )
    monkeypatch.setattr(
        optimize_mod, "emit_optimized_artifact", lambda **_kwargs: out_dir / "artifact.json"
    )

    out_path = out_dir / "clip_optimized.mp4"
    out_path.write_bytes(b"encoded")

    def _fake_run(cmd: list[str], check: bool) -> None:
        _ = check
        commands.append(cmd)
        if cmd[1] == "h264_nvenc":
            raise subprocess.CalledProcessError(255, cmd)

    monkeypatch.setattr(optimize_mod.subprocess, "run", _fake_run)

    outputs = optimize(
        [src],
        out_dir,
        options=OptimizeOptions(mode="transcode", force=True),
    )

    assert outputs == [out_path]
    assert built_encoders == ["h264_nvenc", "libx264"]
    assert commands == [["ffmpeg", "h264_nvenc"], ["ffmpeg", "libx264"]]


def test_optimize_transcode_respects_forced_encoder_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    monkeypatch.setattr(
        optimize_mod,
        "build_optimize_transcode_args",
        lambda *_args, **kwargs: ["ffmpeg", kwargs["encoder"]],
    )
    monkeypatch.setattr(
        optimize_mod,
        "emit_optimize_run",
        lambda **_kwargs: ("opt_run", out_dir / "cosmos_optimize_run.v1.json"),
    )

    def _always_fail(cmd: list[str], check: bool) -> None:
        _ = check
        raise subprocess.CalledProcessError(255, cmd)

    monkeypatch.setattr(optimize_mod.subprocess, "run", _always_fail)

    with pytest.raises(subprocess.CalledProcessError):
        optimize(
            [src],
            out_dir,
            options=OptimizeOptions(mode="transcode", encoder="h264_nvenc"),
        )


def test_optimize_transcode_records_hardware_attempted_from_runtime_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    monkeypatch.setattr(
        optimize_mod, "choose_encoder_for_video", lambda _p: ("libx264", "h264_nvenc")
    )
    monkeypatch.setattr(
        optimize_mod,
        "build_optimize_transcode_args",
        lambda *_args, **kwargs: ["ffmpeg", kwargs["encoder"]],
    )
    monkeypatch.setattr(
        optimize_mod,
        "emit_optimize_run",
        lambda **_kwargs: ("opt_run", out_dir / "cosmos_optimize_run.v1.json"),
    )

    captured: dict[str, object] = {}

    def _capture_artifact(**kwargs: object) -> Path:
        captured.update(kwargs)
        return out_dir / "artifact.json"

    monkeypatch.setattr(optimize_mod, "emit_optimized_artifact", _capture_artifact)
    monkeypatch.setattr(optimize_mod.subprocess, "run", lambda cmd, check: None)

    out_path = out_dir / "clip_optimized.mp4"
    out_path.write_bytes(b"encoded")

    optimize(
        [src],
        out_dir,
        options=OptimizeOptions(mode="transcode", force=True),
    )

    encode_info = captured["encode_info"]
    assert isinstance(encode_info, dict)
    assert encode_info["impl"] == "libx264"
    assert encode_info["hardware_attempted"] == "h264_nvenc"
