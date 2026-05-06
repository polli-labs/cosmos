from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


def _load_benchmark_module() -> ModuleType:
    path = Path("dev/benchmarks/cosmos_video_decode_benchmark.py").resolve()
    spec = importlib.util.spec_from_file_location("cosmos_video_decode_benchmark", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_request_patterns_match_pol_1185_shapes() -> None:
    module = _load_benchmark_module()

    patterns = {
        pattern.name: pattern
        for pattern in module._request_patterns(
            frame_count=1200,
            stride=180,
            random_count=4,
            random_seed=1185,
            dense_max_indices=16,
            include_duplicate_smoke=True,
            rng=module.random.Random(1185),  # noqa: S311
        )
    }

    assert patterns["dense_stride"].indices == [0, 180, 360, 540, 720, 900, 1080]
    assert patterns["late_single"].indices == [1199]
    assert patterns["late_pair"].indices == [1019, 1199]
    assert patterns["split_sparse"].indices == [0, 599, 1019, 1199]
    assert len(patterns["random_sparse"].indices) == 4
    assert patterns["duplicate_order_smoke"].indices == [1199, 0, 599, 599]


def test_cosmos_video_backend_env_restores_previous_value() -> None:
    module = _load_benchmark_module()
    os.environ["COSMOS_VIDEO_BACKEND"] = "pyav"

    with module._cosmos_video_backend_env("ffmpeg-cli"):
        assert os.environ["COSMOS_VIDEO_BACKEND"] == "ffmpeg-cli"

    assert os.environ["COSMOS_VIDEO_BACKEND"] == "pyav"

    with module._cosmos_video_backend_env(None):
        assert "COSMOS_VIDEO_BACKEND" not in os.environ

    assert os.environ["COSMOS_VIDEO_BACKEND"] == "pyav"
    os.environ.pop("COSMOS_VIDEO_BACKEND", None)


def test_backend_specs_include_torchcodec_case() -> None:
    module = _load_benchmark_module()

    backends = {backend.name: backend for backend in module._backend_specs()}

    assert backends["cosmos_torchcodec"].env_value == "torchcodec"
    assert backends["cosmos_torchcodec"].optional is True


def test_input_path_dedupe_preserves_first_source_label(tmp_path: Path) -> None:
    module = _load_benchmark_module()
    clip = tmp_path / "clip.mp4"
    other = tmp_path / "other.mp4"

    deduped = module._dedupe_path_sources(
        [
            (clip, "explicit"),
            (other, "input-dir"),
            (clip, "input-dir"),
        ]
    )

    assert deduped == [(clip, "explicit"), (other, "input-dir")]


def test_pattern_catalog_matches_first_clip_patterns() -> None:
    module = _load_benchmark_module()
    args = SimpleNamespace(
        random_seed=1185,
        stride=180,
        random_count=4,
        dense_max_indices=16,
        include_duplicate_smoke=True,
    )
    clip = module.ClipSpec(
        path=Path("CLIP18_0000-0020_southern-dogface_on_sage.mp4"),
        source="explicit",
        probe=SimpleNamespace(frame_count=1200),
        bytes=0,
    )

    catalog = module._pattern_catalog(clip, args)
    actual = [module._pattern_payload(pattern) for pattern in module._patterns_for_clip(clip, args)]

    assert catalog == actual


def test_correctness_payload_checks_order_duplicates_and_deltas() -> None:
    module = _load_benchmark_module()
    frames = [
        module.FramePayload(requested_index=2, width=2, height=1, rgb24=b"\x01\x02\x03" * 2),
        module.FramePayload(requested_index=0, width=2, height=1, rgb24=b"\x04\x05\x06" * 2),
        module.FramePayload(requested_index=2, width=2, height=1, rgb24=b"\x01\x02\x03" * 2),
    ]
    reference = [
        module.FramePayload(requested_index=2, width=2, height=1, rgb24=b"\x01\x02\x03" * 2),
        module.FramePayload(requested_index=0, width=2, height=1, rgb24=b"\x04\x05\x06" * 2),
        module.FramePayload(requested_index=2, width=2, height=1, rgb24=b"\x01\x02\x04" * 2),
    ]

    payload: dict[str, Any] = module._correctness_payload(
        candidate=frames,
        reference=reference,
        reference_backend="decord_direct",
        requested_indices=[2, 0, 2],
        expected_width=2,
        expected_height=1,
    )

    assert payload["frame_count_ok"] is True
    assert payload["shape_ok"] is True
    assert payload["request_order_ok"] is True
    assert payload["duplicate_payloads_ok"] is True
    assert payload["compared_frame_count"] == 3
    assert payload["exact_frame_count"] == 2
    assert payload["all_exact"] is False
    assert payload["max_abs_delta"] == 1
    assert payload["mean_abs_delta"] == 2 / 18
