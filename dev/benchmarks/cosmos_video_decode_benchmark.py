#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cosmos.ffmpeg.detect import resolve_ffmpeg_path, resolve_ffprobe_path
from cosmos.sdk.video import RgbFrame, VideoDecodeError, VideoProbe, extract_frames_at_indices
from cosmos.sdk.video import probe_video as cosmos_probe_video

ISSUE_ID = "POL-1185"
SCHEMA_VERSION = "cosmos-video-decode-benchmark-v1"
VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4", ".mts", ".ts", ".webm"}
CORE_BACKENDS = {"cosmos_ffmpeg_cli", "cosmos_auto", "cosmos_default"}


@dataclass(frozen=True, slots=True)
class FramePayload:
    requested_index: int
    width: int
    height: int
    rgb24: bytes


@dataclass(frozen=True, slots=True)
class PatternSpec:
    name: str
    description: str
    indices: list[int]
    parameters: dict[str, int]
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ClipSpec:
    path: Path
    source: str
    probe: VideoProbe
    bytes: int


@dataclass(frozen=True, slots=True)
class BackendSpec:
    name: str
    description: str
    env_value: str | None
    optional: bool
    extractor: Callable[[Path, Sequence[int], VideoProbe], list[FramePayload]]


@dataclass(frozen=True, slots=True)
class Availability:
    available: bool
    reason: str | None = None
    versions: dict[str, str | None] | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark cosmos.sdk.video decode backends against optional Decord.",
    )
    parser.add_argument(
        "--clip",
        dest="clips",
        action="append",
        type=Path,
        default=[],
        help="Input video clip. Repeat for multiple real fixtures.",
    )
    parser.add_argument(
        "--input-dir",
        dest="input_dirs",
        action="append",
        type=Path,
        default=[],
        help="Directory to scan for video clips when --clip is not enough.",
    )
    parser.add_argument(
        "--glob",
        default="**/*",
        help="Glob used with --input-dir before filtering known video extensions.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Benchmark output directory. Defaults to _work/pol-1185/<timestamp>.",
    )
    parser.add_argument("--repeats", type=int, default=3, help="Measured repeats per case.")
    parser.add_argument("--warmup", type=int, default=0, help="Warmup repeats per case.")
    parser.add_argument("--stride", type=int, default=180, help="Stride for dense/late patterns.")
    parser.add_argument(
        "--random-count",
        type=int,
        default=6,
        help="Number of random sparse indices per clip.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=1185,
        help="Deterministic seed for random_sparse patterns.",
    )
    parser.add_argument(
        "--dense-max-indices",
        type=int,
        default=16,
        help="Cap dense_stride requests to avoid accidental huge runs; use 0 for no cap.",
    )
    parser.add_argument(
        "--include-duplicate-smoke",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include a duplicate/order smoke request in correctness output.",
    )
    parser.add_argument(
        "--synthetic-count",
        type=int,
        default=1,
        help="Synthetic clips to generate when no real clip is provided.",
    )
    parser.add_argument(
        "--synthetic-frames",
        type=int,
        default=720,
        help="Frame count for generated synthetic fixtures.",
    )
    parser.add_argument(
        "--synthetic-fps",
        type=float,
        default=60.0,
        help="Frame rate for generated synthetic fixtures.",
    )
    parser.add_argument(
        "--synthetic-size",
        default="426x240",
        help="Synthetic fixture dimensions as WIDTHxHEIGHT.",
    )
    parser.add_argument(
        "--no-synthetic",
        action="store_true",
        help="Fail instead of generating synthetic clips when no input clips are found.",
    )
    parser.add_argument(
        "--fail-on-core-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit non-zero if a core Cosmos backend errors on any case.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    _validate_args(args)
    created_at = _utc_now()
    out_dir = (args.out_dir or _default_out_dir(created_at)).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir = out_dir.resolve()

    artifact_paths = _artifact_paths(out_dir)
    clips = _resolve_clips(args, out_dir / "fixtures")
    backends = _backend_specs()
    availability = _backend_availability(backends)

    results: list[dict[str, Any]] = []
    fatal_errors: list[str] = []
    for clip in clips:
        clip_results, clip_errors = _benchmark_clip(
            clip=clip,
            backends=backends,
            availability=availability,
            args=args,
        )
        results.extend(clip_results)
        fatal_errors.extend(clip_errors)

    report = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_ID,
        "created_at": created_at,
        "environment": _environment_payload(),
        "configuration": _configuration_payload(args),
        "backend_availability": {
            name: _availability_payload(item) for name, item in availability.items()
        },
        "clips": [_clip_payload(clip) for clip in clips],
        "pattern_catalog": _pattern_catalog(clips[0], args) if clips else [],
        "results": results,
        "summary": _summary_payload(results),
        "raw_artifacts": {key: str(path) for key, path in artifact_paths.items()},
    }

    _write_json(artifact_paths["json"], report)
    _write_timings_csv(artifact_paths["timings_csv"], results)
    _write_correctness_csv(artifact_paths["correctness_csv"], results)
    _write_summary_markdown(artifact_paths["summary_md"], report)

    _stderr(f"Wrote benchmark JSON: {artifact_paths['json']}\n")
    _stderr(f"Wrote benchmark summary: {artifact_paths['summary_md']}\n")
    if fatal_errors and args.fail_on_core_error:
        _stderr("Core backend errors were recorded:\n")
        for error in fatal_errors:
            _stderr(f"- {error}\n")
        return 1
    return 0


def _validate_args(args: argparse.Namespace) -> None:
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    if args.warmup < 0:
        raise SystemExit("--warmup must be >= 0")
    if args.stride < 1:
        raise SystemExit("--stride must be >= 1")
    if args.random_count < 1:
        raise SystemExit("--random-count must be >= 1")
    if args.dense_max_indices < 0:
        raise SystemExit("--dense-max-indices must be >= 0")
    if args.synthetic_count < 0:
        raise SystemExit("--synthetic-count must be >= 0")
    if args.synthetic_frames < 2:
        raise SystemExit("--synthetic-frames must be >= 2")
    if args.synthetic_fps <= 0:
        raise SystemExit("--synthetic-fps must be > 0")
    _parse_size(args.synthetic_size)


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _default_out_dir(created_at: str) -> Path:
    stamp = created_at.replace(":", "").replace("-", "").replace("Z", "Z")
    return Path("_work") / "pol-1185" / f"video-decode-benchmark-{stamp}"


def _artifact_paths(out_dir: Path) -> dict[str, Path]:
    return {
        "json": out_dir / "cosmos_video_decode_benchmark.v1.json",
        "timings_csv": out_dir / "cosmos_video_decode_timings.csv",
        "correctness_csv": out_dir / "cosmos_video_decode_correctness.csv",
        "summary_md": out_dir / "cosmos_video_decode_summary.md",
    }


def _resolve_clips(args: argparse.Namespace, fixtures_dir: Path) -> list[ClipSpec]:
    path_sources = _discover_input_paths(args.clips, args.input_dirs, args.glob)
    if not path_sources:
        if args.no_synthetic or args.synthetic_count == 0:
            raise SystemExit("No input clips found and synthetic generation is disabled.")
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        path_sources = [
            (path, "synthetic")
            for path in _generate_synthetic_clips(
                fixtures_dir=fixtures_dir,
                count=args.synthetic_count,
                frames=args.synthetic_frames,
                fps=args.synthetic_fps,
                size=args.synthetic_size,
            )
        ]

    clips: list[ClipSpec] = []
    for path, source in path_sources:
        probe = cosmos_probe_video(path)
        clips.append(
            ClipSpec(
                path=path,
                source=source,
                probe=probe,
                bytes=path.stat().st_size,
            )
        )
    return clips


def _discover_input_paths(
    explicit_clips: Sequence[Path],
    input_dirs: Sequence[Path],
    pattern: str,
) -> list[tuple[Path, str]]:
    discovered: list[tuple[Path, str]] = []
    for clip in explicit_clips:
        path = clip.expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Input clip does not exist: {path}")
        discovered.append((path, "explicit"))

    for directory in input_dirs:
        root = directory.expanduser().resolve()
        if not root.exists():
            raise SystemExit(f"Input directory does not exist: {root}")
        if not root.is_dir():
            raise SystemExit(f"Input path is not a directory: {root}")
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS:
                discovered.append((candidate.resolve(), "input-dir"))

    return _dedupe_path_sources(discovered)


def _dedupe_path_sources(paths: Sequence[tuple[Path, str]]) -> list[tuple[Path, str]]:
    seen: set[Path] = set()
    deduped: list[tuple[Path, str]] = []
    for path, source in paths:
        if path not in seen:
            seen.add(path)
            deduped.append((path, source))
    return deduped


def _generate_synthetic_clips(
    *,
    fixtures_dir: Path,
    count: int,
    frames: int,
    fps: float,
    size: str,
) -> list[Path]:
    width, height = _parse_size(size)
    generated: list[Path] = []
    for offset in range(count):
        clip_path = fixtures_dir / (
            f"synthetic_{offset + 1:02d}_{width}x{height}_{frames}f_{fps:g}fps.mp4"
        )
        if not clip_path.exists():
            _generate_synthetic_clip(clip_path, frames=frames, fps=fps, size=size, offset=offset)
        generated.append(clip_path.resolve())
    return generated


def _parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise SystemExit("--synthetic-size must look like WIDTHxHEIGHT")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise SystemExit("--synthetic-size width and height must be integers") from exc
    if width <= 0 or height <= 0:
        raise SystemExit("--synthetic-size width and height must be positive")
    if width % 2 or height % 2:
        raise SystemExit("--synthetic-size width and height must be even for yuv420p")
    return width, height


def _generate_synthetic_clip(
    path: Path,
    *,
    frames: int,
    fps: float,
    size: str,
    offset: int,
) -> None:
    rate = f"{fps:g}"
    hue = (offset * 37) % 360
    filtergraph = f"testsrc2=size={size}:rate={rate},hue=h={hue}:s=1,format=yuv420p"
    cmd = [
        resolve_ffmpeg_path(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        filtergraph,
        "-frames:v",
        str(frames),
        "-c:v",
        "mpeg4",
        "-g",
        str(max(12, min(frames, int(round(fps * 3))))),
        "-bf",
        "0",
        "-q:v",
        "3",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603


def _backend_specs() -> list[BackendSpec]:
    return [
        BackendSpec(
            name="cosmos_ffmpeg_cli",
            description="cosmos.sdk.video with COSMOS_VIDEO_BACKEND=ffmpeg-cli",
            env_value="ffmpeg-cli",
            optional=False,
            extractor=_extract_cosmos_frames,
        ),
        BackendSpec(
            name="cosmos_pyav",
            description="cosmos.sdk.video with COSMOS_VIDEO_BACKEND=pyav",
            env_value="pyav",
            optional=True,
            extractor=_extract_cosmos_frames,
        ),
        BackendSpec(
            name="cosmos_torchcodec",
            description="cosmos.sdk.video with COSMOS_VIDEO_BACKEND=torchcodec",
            env_value="torchcodec",
            optional=True,
            extractor=_extract_cosmos_frames,
        ),
        BackendSpec(
            name="cosmos_auto",
            description="cosmos.sdk.video with COSMOS_VIDEO_BACKEND=auto",
            env_value="auto",
            optional=False,
            extractor=_extract_cosmos_frames,
        ),
        BackendSpec(
            name="cosmos_default",
            description="cosmos.sdk.video with COSMOS_VIDEO_BACKEND unset",
            env_value=None,
            optional=False,
            extractor=_extract_cosmos_frames,
        ),
        BackendSpec(
            name="decord_direct",
            description="direct Decord VideoReader.get_batch comparator",
            env_value=None,
            optional=True,
            extractor=_extract_decord_frames,
        ),
    ]


def _backend_availability(backends: Sequence[BackendSpec]) -> dict[str, Availability]:
    ffmpeg_available, ffmpeg_reason = _command_available(resolve_ffmpeg_path)
    availability: dict[str, Availability] = {}
    for backend in backends:
        versions = _backend_versions(backend.name)
        if backend.name == "cosmos_pyav":
            availability[backend.name] = _optional_import_availability(("av", "numpy"), versions)
        elif backend.name == "cosmos_torchcodec":
            availability[backend.name] = _optional_import_availability(
                ("torch", "torchcodec.decoders", "numpy"), versions
            )
        elif backend.name == "decord_direct":
            availability[backend.name] = _optional_import_availability(
                ("decord", "numpy"), versions
            )
        elif ffmpeg_available:
            availability[backend.name] = Availability(available=True, versions=versions)
        else:
            availability[backend.name] = Availability(
                available=False,
                reason=ffmpeg_reason or "ffmpeg unavailable",
                versions=versions,
            )
    return availability


def _command_available(resolver: Callable[[], str]) -> tuple[bool, str | None]:
    try:
        executable = resolver()
        subprocess.run([executable, "-version"], check=True, capture_output=True)  # noqa: S603
    except Exception as exc:  # pragma: no cover - host-specific error text
        return False, str(exc)
    return True, None


def _optional_import_availability(
    module_names: Sequence[str],
    versions: dict[str, str | None],
) -> Availability:
    missing: list[str] = []
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
        except (
            Exception
        ) as exc:  # pragma: no cover - optional binary import health is host-specific
            return Availability(
                available=False,
                reason=f"{module_name} import failed: {type(exc).__name__}: {exc}",
                versions=versions,
            )
    if missing:
        return Availability(
            available=False,
            reason=f"missing optional module(s): {', '.join(missing)}",
            versions=versions,
        )
    return Availability(available=True, versions=versions)


def _backend_versions(backend_name: str) -> dict[str, str | None]:
    versions = {"polli-cosmos": _package_version("polli-cosmos")}
    if backend_name == "cosmos_pyav":
        versions["av"] = _package_version("av")
        versions["numpy"] = _package_version("numpy")
    if backend_name == "cosmos_torchcodec":
        versions["torch"] = _package_version("torch")
        versions["torchcodec"] = _package_version("torchcodec")
        versions["numpy"] = _package_version("numpy")
    if backend_name == "decord_direct":
        versions["decord"] = _package_version("decord")
        versions["numpy"] = _package_version("numpy")
    return versions


def _package_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _benchmark_clip(
    *,
    clip: ClipSpec,
    backends: Sequence[BackendSpec],
    availability: dict[str, Availability],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[str]]:
    patterns = _patterns_for_clip(clip, args)
    results: list[dict[str, Any]] = []
    fatal_errors: list[str] = []
    for pattern in patterns:
        pattern_result, pattern_errors = _benchmark_pattern(
            clip=clip,
            pattern=pattern,
            backends=backends,
            availability=availability,
            repeats=args.repeats,
            warmup=args.warmup,
        )
        results.append(pattern_result)
        fatal_errors.extend(pattern_errors)
    return results, fatal_errors


def _patterns_for_clip(clip: ClipSpec, args: argparse.Namespace) -> list[PatternSpec]:
    rng = random.Random(args.random_seed + _stable_int(clip.path.name))  # noqa: S311
    return _request_patterns(
        frame_count=clip.probe.frame_count,
        stride=args.stride,
        random_count=args.random_count,
        random_seed=args.random_seed,
        dense_max_indices=args.dense_max_indices,
        include_duplicate_smoke=args.include_duplicate_smoke,
        rng=rng,
    )


def _request_patterns(
    *,
    frame_count: int | None,
    stride: int,
    random_count: int,
    random_seed: int,
    dense_max_indices: int,
    include_duplicate_smoke: bool,
    rng: random.Random,
) -> list[PatternSpec]:
    count = frame_count or max(stride * 6, random_count)
    last = max(0, count - 1)
    middle = last // 2
    dense = list(range(0, count, stride)) or [0]
    dense, dense_truncated = _cap_indices(dense, dense_max_indices)

    patterns = [
        PatternSpec(
            name="dense_stride",
            description="Every Nth decoded frame from the start of the clip.",
            indices=dense,
            parameters={"stride": stride, "dense_max_indices": dense_max_indices},
            truncated=dense_truncated,
        ),
        PatternSpec(
            name="late_single",
            description="Single decoded frame near the end of the clip.",
            indices=[last],
            parameters={"stride": stride},
        ),
        PatternSpec(
            name="late_pair",
            description="Two decoded frames near the end of the clip.",
            indices=_unique_in_order([max(0, last - stride), last]),
            parameters={"stride": stride},
        ),
        PatternSpec(
            name="split_sparse",
            description="Sparse request split across the beginning, middle, and end.",
            indices=_unique_in_order([0, middle, max(0, last - stride), last]),
            parameters={"stride": stride},
        ),
        PatternSpec(
            name="random_sparse",
            description="Deterministic random sparse request, preserving sampled order.",
            indices=_random_indices(count, random_count, rng),
            parameters={"random_count": random_count, "random_seed": random_seed},
        ),
    ]
    if include_duplicate_smoke:
        patterns.append(
            PatternSpec(
                name="duplicate_order_smoke",
                description="Correctness smoke for request order and duplicate indices.",
                indices=[last, 0, middle, middle],
                parameters={"stride": stride},
            )
        )
    return patterns


def _cap_indices(indices: Sequence[int], max_indices: int) -> tuple[list[int], bool]:
    if max_indices and len(indices) > max_indices:
        return list(indices[:max_indices]), True
    return list(indices), False


def _unique_in_order(indices: Sequence[int]) -> list[int]:
    seen: set[int] = set()
    unique: list[int] = []
    for index in indices:
        if index not in seen:
            seen.add(index)
            unique.append(index)
    return unique


def _random_indices(count: int, random_count: int, rng: random.Random) -> list[int]:
    size = min(count, random_count)
    if size <= 0:
        return []
    return rng.sample(range(count), size)


def _stable_int(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _benchmark_pattern(
    *,
    clip: ClipSpec,
    pattern: PatternSpec,
    backends: Sequence[BackendSpec],
    availability: dict[str, Availability],
    repeats: int,
    warmup: int,
) -> tuple[dict[str, Any], list[str]]:
    backend_payloads: dict[str, list[FramePayload]] = {}
    backend_results: list[dict[str, Any]] = []
    fatal_errors: list[str] = []

    for backend in backends:
        result, payloads = _run_backend_case(
            backend=backend,
            available=availability[backend.name],
            clip=clip,
            pattern=pattern,
            repeats=repeats,
            warmup=warmup,
        )
        if payloads is not None:
            backend_payloads[backend.name] = payloads
        if result.get("status") == "error" and backend.name in CORE_BACKENDS:
            fatal_errors.append(f"{backend.name} failed for {clip.path.name}/{pattern.name}")
        backend_results.append(result)

    reference_backend = _choose_reference_backend(backend_payloads)
    for result in backend_results:
        payloads = backend_payloads.get(str(result["backend"]))
        result["correctness"] = _correctness_payload(
            candidate=payloads,
            reference=backend_payloads.get(reference_backend) if reference_backend else None,
            reference_backend=reference_backend,
            requested_indices=pattern.indices,
            expected_width=clip.probe.width,
            expected_height=clip.probe.height,
        )

    return (
        {
            "clip": str(clip.path),
            "clip_name": clip.path.name,
            "pattern": pattern.name,
            "pattern_definition": _pattern_payload(pattern),
            "requested_indices": pattern.indices,
            "reference_backend": reference_backend,
            "backends": backend_results,
        },
        fatal_errors,
    )


def _run_backend_case(
    *,
    backend: BackendSpec,
    available: Availability,
    clip: ClipSpec,
    pattern: PatternSpec,
    repeats: int,
    warmup: int,
) -> tuple[dict[str, Any], list[FramePayload] | None]:
    base = {
        "backend": backend.name,
        "description": backend.description,
        "env": {"COSMOS_VIDEO_BACKEND": backend.env_value},
        "optional": backend.optional,
        "timings_seconds": [],
    }
    if not available.available:
        return (
            {
                **base,
                "status": "skipped",
                "reason": available.reason,
                "timing": None,
                "frame_digests": [],
            },
            None,
        )

    payloads: list[FramePayload] | None = None
    try:
        with _cosmos_video_backend_env(backend.env_value):
            for _ in range(warmup):
                backend.extractor(clip.path, pattern.indices, clip.probe)
            timings: list[float] = []
            for _ in range(repeats):
                gc.collect()
                start = time.perf_counter()
                payloads = backend.extractor(clip.path, pattern.indices, clip.probe)
                timings.append(time.perf_counter() - start)
    except Exception as exc:
        return (
            {
                **base,
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
                "timing": None,
                "frame_digests": [],
            },
            None,
        )

    return (
        {
            **base,
            "status": "ok",
            "reason": None,
            "timings_seconds": timings,
            "timing": _timing_payload(timings),
            "frame_digests": _frame_digests(payloads or []),
        },
        payloads,
    )


@contextmanager
def _cosmos_video_backend_env(value: str | None) -> Iterator[None]:
    previous = os.environ.get("COSMOS_VIDEO_BACKEND")
    try:
        if value is None:
            os.environ.pop("COSMOS_VIDEO_BACKEND", None)
        else:
            os.environ["COSMOS_VIDEO_BACKEND"] = value
        yield
    finally:
        if previous is None:
            os.environ.pop("COSMOS_VIDEO_BACKEND", None)
        else:
            os.environ["COSMOS_VIDEO_BACKEND"] = previous


def _extract_cosmos_frames(
    path: Path,
    indices: Sequence[int],
    probe: VideoProbe,
) -> list[FramePayload]:
    frames = extract_frames_at_indices(path, indices, probe=probe)
    return [_from_rgb_frame(frame) for frame in frames]


def _from_rgb_frame(frame: RgbFrame) -> FramePayload:
    if frame.requested_index is None:
        raise VideoDecodeError("cosmos index extraction returned a frame without requested_index")
    return FramePayload(
        requested_index=frame.requested_index,
        width=frame.width,
        height=frame.height,
        rgb24=frame.rgb24,
    )


def _extract_decord_frames(
    path: Path,
    indices: Sequence[int],
    probe: VideoProbe,
) -> list[FramePayload]:
    decord = importlib.import_module("decord")
    video_reader = decord.VideoReader(str(path), ctx=decord.cpu(0))
    batch = video_reader.get_batch(list(indices)).asnumpy()
    if len(batch.shape) != 4 or batch.shape[3] != 3:
        raise VideoDecodeError(f"Decord returned unexpected batch shape: {batch.shape!r}")
    height = int(batch.shape[1])
    width = int(batch.shape[2])
    if width != probe.width or height != probe.height:
        raise VideoDecodeError(
            f"Decord shape {width}x{height} does not match probe {probe.width}x{probe.height}"
        )
    return [
        FramePayload(
            requested_index=index,
            width=width,
            height=height,
            rgb24=batch[offset].tobytes(),
        )
        for offset, index in enumerate(indices)
    ]


def _timing_payload(timings: Sequence[float]) -> dict[str, float | int]:
    return {
        "repeats": len(timings),
        "median_seconds": statistics.median(timings),
        "min_seconds": min(timings),
        "max_seconds": max(timings),
        "mean_seconds": statistics.fmean(timings),
    }


def _frame_digests(frames: Sequence[FramePayload]) -> list[dict[str, Any]]:
    return [
        {
            "requested_index": frame.requested_index,
            "width": frame.width,
            "height": frame.height,
            "sha256_16": hashlib.sha256(frame.rgb24).hexdigest()[:16],
            "bytes": len(frame.rgb24),
        }
        for frame in frames
    ]


def _choose_reference_backend(payloads: dict[str, list[FramePayload]]) -> str | None:
    for preferred in ("decord_direct", "cosmos_ffmpeg_cli", "cosmos_default", "cosmos_auto"):
        if preferred in payloads:
            return preferred
    return next(iter(payloads), None)


def _correctness_payload(
    *,
    candidate: list[FramePayload] | None,
    reference: list[FramePayload] | None,
    reference_backend: str | None,
    requested_indices: Sequence[int],
    expected_width: int,
    expected_height: int,
) -> dict[str, Any]:
    if candidate is None:
        return {
            "available": False,
            "reference_backend": reference_backend,
            "frame_count_ok": False,
            "shape_ok": False,
            "request_order_ok": False,
            "duplicate_payloads_ok": None,
            "compared_frame_count": 0,
            "exact_frame_count": 0,
            "all_exact": None,
            "max_abs_delta": None,
            "mean_abs_delta": None,
        }

    frame_count_ok = len(candidate) == len(requested_indices)
    shape_ok = all(
        frame.width == expected_width and frame.height == expected_height for frame in candidate
    )
    request_order_ok = [frame.requested_index for frame in candidate] == list(requested_indices)
    duplicate_payloads_ok = _duplicate_payloads_ok(candidate)
    delta = _delta_payload(candidate, reference)

    return {
        "available": True,
        "reference_backend": reference_backend,
        "frame_count_ok": frame_count_ok,
        "shape_ok": shape_ok,
        "request_order_ok": request_order_ok,
        "duplicate_payloads_ok": duplicate_payloads_ok,
        **delta,
    }


def _duplicate_payloads_ok(frames: Sequence[FramePayload]) -> bool | None:
    seen: dict[int, bytes] = {}
    has_duplicate = False
    for frame in frames:
        previous = seen.get(frame.requested_index)
        if previous is None:
            seen[frame.requested_index] = frame.rgb24
            continue
        has_duplicate = True
        if previous != frame.rgb24:
            return False
    if not has_duplicate:
        return None
    return True


def _delta_payload(
    candidate: Sequence[FramePayload],
    reference: Sequence[FramePayload] | None,
) -> dict[str, Any]:
    if reference is None:
        return {
            "compared_frame_count": 0,
            "exact_frame_count": 0,
            "all_exact": None,
            "max_abs_delta": None,
            "mean_abs_delta": None,
        }

    compared = min(len(candidate), len(reference))
    exact_frames = 0
    max_delta = 0
    total_delta = 0
    total_values = 0
    for left, right in zip(candidate[:compared], reference[:compared], strict=False):
        if left.rgb24 == right.rgb24:
            exact_frames += 1
        frame_delta = _bytes_delta(left.rgb24, right.rgb24)
        max_delta = max(max_delta, frame_delta["max_abs_delta"])
        total_delta += frame_delta["sum_abs_delta"]
        total_values += frame_delta["values"]

    mean_delta = (total_delta / total_values) if total_values else None
    return {
        "compared_frame_count": compared,
        "exact_frame_count": exact_frames,
        "all_exact": exact_frames == compared and len(candidate) == len(reference),
        "max_abs_delta": max_delta if total_values else None,
        "mean_abs_delta": mean_delta,
    }


def _bytes_delta(left: bytes, right: bytes) -> dict[str, int]:
    if len(left) != len(right):
        raise VideoDecodeError(
            f"Cannot compare frame bytes with different lengths: {len(left)} != {len(right)}"
        )

    numpy_delta = _numpy_bytes_delta(left, right)
    if numpy_delta is not None:
        return numpy_delta

    max_abs = 0
    sum_abs = 0
    for left_value, right_value in zip(left, right, strict=True):
        delta = abs(left_value - right_value)
        max_abs = max(max_abs, delta)
        sum_abs += delta
    return {"max_abs_delta": max_abs, "sum_abs_delta": sum_abs, "values": len(left)}


def _numpy_bytes_delta(left: bytes, right: bytes) -> dict[str, int] | None:
    try:
        numpy = importlib.import_module("numpy")
    except ModuleNotFoundError:
        return None
    left_array = numpy.frombuffer(left, dtype=numpy.uint8).astype(numpy.int16)
    right_array = numpy.frombuffer(right, dtype=numpy.uint8).astype(numpy.int16)
    delta = numpy.abs(left_array - right_array)
    return {
        "max_abs_delta": int(delta.max(initial=0)),
        "sum_abs_delta": int(delta.sum()),
        "values": int(delta.size),
    }


def _environment_payload() -> dict[str, Any]:
    return {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "cwd": str(Path.cwd()),
        "git": _git_payload(),
        "ffmpeg": _binary_payload(resolve_ffmpeg_path),
        "ffprobe": _binary_payload(resolve_ffprobe_path),
        "packages": {
            "polli-cosmos": _package_version("polli-cosmos"),
            "av": _package_version("av"),
            "decord": _package_version("decord"),
            "numpy": _package_version("numpy"),
            "torch": _package_version("torch"),
            "torchcodec": _package_version("torchcodec"),
        },
    }


def _git_payload() -> dict[str, str | None]:
    return {
        "branch": _run_text(["git", "branch", "--show-current"]),
        "commit": _run_text(["git", "rev-parse", "HEAD"]),
        "origin_main": _run_text(["git", "rev-parse", "origin/main"]),
    }


def _binary_payload(resolver: Callable[[], str]) -> dict[str, str | None]:
    try:
        executable = resolver()
    except Exception as exc:  # pragma: no cover - host-specific error text
        return {"path": None, "version": f"{type(exc).__name__}: {exc}"}
    return {"path": executable, "version": _run_text([executable, "-version"], first_line=True)}


def _run_text(cmd: Sequence[str], *, first_line: bool = False) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603
            list(cmd),
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    text = completed.stdout.strip()
    if first_line:
        return text.splitlines()[0] if text else None
    return text or None


def _configuration_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "repeats": args.repeats,
        "warmup": args.warmup,
        "stride": args.stride,
        "random_count": args.random_count,
        "random_seed": args.random_seed,
        "dense_max_indices": args.dense_max_indices,
        "include_duplicate_smoke": args.include_duplicate_smoke,
        "synthetic_count": args.synthetic_count,
        "synthetic_frames": args.synthetic_frames,
        "synthetic_fps": args.synthetic_fps,
        "synthetic_size": args.synthetic_size,
    }


def _clip_payload(clip: ClipSpec) -> dict[str, Any]:
    return {
        "path": str(clip.path),
        "source": clip.source,
        "bytes": clip.bytes,
        "metadata": {
            "width": clip.probe.width,
            "height": clip.probe.height,
            "duration_seconds": clip.probe.duration_seconds,
            "fps": clip.probe.fps,
            "frame_count": clip.probe.frame_count,
            "codec_name": clip.probe.codec_name,
            "codec_long_name": clip.probe.codec_long_name,
            "format_name": clip.probe.format_name,
        },
    }


def _pattern_catalog(clip: ClipSpec, args: argparse.Namespace) -> list[dict[str, Any]]:
    return [_pattern_payload(pattern) for pattern in _patterns_for_clip(clip, args)]


def _pattern_payload(pattern: PatternSpec) -> dict[str, Any]:
    return {
        "name": pattern.name,
        "description": pattern.description,
        "parameters": pattern.parameters,
        "truncated": pattern.truncated,
    }


def _availability_payload(item: Availability) -> dict[str, Any]:
    return {
        "available": item.available,
        "reason": item.reason,
        "versions": item.versions or {},
    }


def _summary_payload(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    medians: dict[str, dict[str, list[float]]] = {}
    for result in results:
        pattern = str(result["pattern"])
        medians.setdefault(pattern, {})
        for backend in result["backends"]:
            timing = backend.get("timing")
            if not isinstance(timing, dict):
                continue
            median = timing.get("median_seconds")
            if isinstance(median, int | float):
                medians[pattern].setdefault(str(backend["backend"]), []).append(float(median))

    by_pattern: dict[str, dict[str, float]] = {}
    for pattern, backend_values in medians.items():
        by_pattern[pattern] = {
            backend: statistics.median(values)
            for backend, values in sorted(backend_values.items())
            if values
        }

    return {
        "clip_count": len({str(result["clip"]) for result in results}),
        "pattern_count": len({str(result["pattern"]) for result in results}),
        "median_seconds_by_pattern_backend": by_pattern,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_timings_csv(path: Path, results: Sequence[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for result in results:
        for backend in result["backends"]:
            timing = backend.get("timing") or {}
            rows.append(
                {
                    "clip": result["clip_name"],
                    "pattern": result["pattern"],
                    "backend": backend["backend"],
                    "status": backend["status"],
                    "reason": backend["reason"],
                    "repeat_count": timing.get("repeats"),
                    "median_seconds": timing.get("median_seconds"),
                    "min_seconds": timing.get("min_seconds"),
                    "max_seconds": timing.get("max_seconds"),
                    "mean_seconds": timing.get("mean_seconds"),
                    "timings_seconds_json": json.dumps(backend.get("timings_seconds", [])),
                }
            )
    _write_csv(path, rows)


def _write_correctness_csv(path: Path, results: Sequence[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for result in results:
        for backend in result["backends"]:
            correctness = backend["correctness"]
            rows.append(
                {
                    "clip": result["clip_name"],
                    "pattern": result["pattern"],
                    "backend": backend["backend"],
                    "status": backend["status"],
                    "reference_backend": correctness["reference_backend"],
                    "frame_count_ok": correctness["frame_count_ok"],
                    "shape_ok": correctness["shape_ok"],
                    "request_order_ok": correctness["request_order_ok"],
                    "duplicate_payloads_ok": correctness["duplicate_payloads_ok"],
                    "compared_frame_count": correctness["compared_frame_count"],
                    "exact_frame_count": correctness["exact_frame_count"],
                    "all_exact": correctness["all_exact"],
                    "max_abs_delta": correctness["max_abs_delta"],
                    "mean_abs_delta": correctness["mean_abs_delta"],
                }
            )
    _write_csv(path, rows)


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_summary_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Cosmos Video Decode Benchmark",
        "",
        f"- issue: `{report['issue']}`",
        f"- created: `{report['created_at']}`",
        f"- host: `{report['environment']['host']}`",
        f"- git commit: `{report['environment']['git']['commit']}`",
        "",
        "## Artifacts",
        "",
    ]
    for key, artifact_path in report["raw_artifacts"].items():
        lines.append(f"- {key}: `{artifact_path}`")
    lines.extend(["", "## Backend Availability", ""])
    for name, item in report["backend_availability"].items():
        status = "available" if item["available"] else f"skipped: {item['reason']}"
        lines.append(f"- `{name}`: {status}")
    lines.extend(["", "## Median Seconds By Pattern", ""])
    lines.append("| Pattern | Backend | Median seconds |")
    lines.append("| --- | --- | ---: |")
    for pattern, backends in report["summary"]["median_seconds_by_pattern_backend"].items():
        for backend, median_seconds in backends.items():
            lines.append(f"| `{pattern}` | `{backend}` | {median_seconds:.6f} |")
    lines.extend(["", "## Clips", ""])
    lines.append("| Clip | Resolution | FPS | Frames | Source |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for clip in report["clips"]:
        metadata = clip["metadata"]
        lines.append(
            "| "
            f"`{Path(clip['path']).name}` | "
            f"{metadata['width']}x{metadata['height']} | "
            f"{_format_optional_float(metadata['fps'])} | "
            f"{metadata['frame_count']} | "
            f"{clip['source']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_optional_float(value: object) -> str:
    return f"{value:.3f}" if isinstance(value, int | float) else ""


def _stderr(message: str) -> None:
    sys.stderr.write(message)


if __name__ == "__main__":
    raise SystemExit(main())
