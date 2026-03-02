from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from cosmos.ingest.adapter import ClipDescriptor
from cosmos.ingest.adapters import resolve_adapter
from cosmos.ingest.preflight import preflight
from cosmos.ingest.processor import (
    ProcessingMode,
    ProcessingOptions,
    ProcessingResult,
    VideoProcessor,
)
from cosmos.sdk.provenance import (
    emit_clip_artifact,
    emit_ingest_run,
    ffprobe_video,
)
from cosmos.utils.io import ensure_dir

_log = logging.getLogger(__name__)


@dataclass
class IngestOptions:
    width: int = 3840
    height: int = 2160
    quality_mode: str = "balanced"  # quality|balanced|performance|minimal|low_memory
    low_memory: bool = False
    crf: int | None = None
    dry_run: bool = False
    clips: list[str] | None = None
    scale_filter: str | None = None
    filter_threads: int | None = None
    filter_complex_threads: int | None = None
    decode: str = "auto"  # auto|hw|sw
    window_seconds: float | None = None
    adapter: str | None = None  # explicit adapter name; None = auto-detect
    profile: str | None = None  # determinism profile name; None = legacy behaviour


def ingest(  # noqa: C901
    input_dir: Path,
    output_dir: Path,
    *,
    manifest: Path | None = None,
    options: IngestOptions,
) -> list[Path]:
    """Run ingest through the adapter contract and return generated MP4 paths.

    Parameters
    ----------
    input_dir:
        Root directory of the source media.
    output_dir:
        Where to write output MP4s and provenance artifacts.
    manifest:
        Legacy parameter kept for backward compatibility. When provided, it
        is forwarded to the COSM adapter as a hint.  For non-COSM adapters
        it is silently ignored.
    options:
        Ingest configuration knobs.
    """
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory not found: {input_dir}")
    ensure_dir(output_dir)
    preflight(input_dir)

    # -- resolve adapter ------------------------------------------------------
    adapter = resolve_adapter(input_dir, adapter_name=options.adapter)
    _log.info("Using ingest adapter: %s", adapter.name)

    # -- system pre-checks ----------------------------------------------------
    adapter.validate_system(output_dir)

    # -- discover clips -------------------------------------------------------
    all_clips = adapter.discover_clips(input_dir)
    if options.clips:
        wanted = {c.upper() for c in options.clips}
        clips_iter = [c for c in all_clips if c.name.upper() in wanted]
    else:
        clips_iter = all_clips

    if not clips_iter:
        _log.warning("No clips discovered by adapter %r in %s", adapter.name, input_dir)
        return []

    # Keep legacy manifest provenance behavior for COSM auto-detect runs.
    manifest_for_run = manifest
    if manifest_for_run is None and adapter.name == "cosm":
        maybe_manifest = next(
            (
                clip.extra.get("_manifest_path")
                for clip in all_clips
                if isinstance(clip.extra.get("_manifest_path"), Path)
            ),
            None,
        )
        if isinstance(maybe_manifest, Path):
            manifest_for_run = maybe_manifest

    # -- resolve determinism profile ------------------------------------------
    from cosmos.sdk.profiles import resolve_profile

    profile = resolve_profile(options.profile)

    # Apply profile defaults where the caller did not set an explicit value.
    effective_filter_threads = options.filter_threads
    effective_fc_threads = options.filter_complex_threads
    effective_scale_filter = options.scale_filter
    if profile is not None:
        if effective_filter_threads is None and profile.threads is not None:
            effective_filter_threads = profile.threads
        if effective_fc_threads is None and profile.threads is not None:
            effective_fc_threads = profile.threads
        if effective_scale_filter is None and profile.scale_filter is not None:
            effective_scale_filter = profile.scale_filter

    # -- prepare processor (encoder detection, options) -----------------------
    mode_map = {
        "quality": ProcessingMode.QUALITY,
        "balanced": ProcessingMode.BALANCED,
        "performance": ProcessingMode.PERFORMANCE,
        "low_memory": ProcessingMode.LOW_MEMORY,
        "minimal": ProcessingMode.MINIMAL,
    }
    quality = mode_map.get(options.quality_mode.lower(), ProcessingMode.BALANCED)
    scale_filter = effective_scale_filter or (
        "lanczos" if quality == ProcessingMode.QUALITY else "bicubic"
    )
    proc_opts = ProcessingOptions(
        output_resolution=(options.width, options.height),
        quality_mode=quality,
        low_memory=options.low_memory,
        crf=options.crf,
    )
    po = cast(Any, proc_opts)
    po.scale_filter = scale_filter
    po.filter_threads = effective_filter_threads
    po.filter_complex_threads = effective_fc_threads
    po.decode = options.decode
    po.window_seconds = options.window_seconds
    po.bitexact = profile.bitexact if profile else False
    po.pinned_encoder = profile.pinned_encoder if profile else None
    processor = VideoProcessor(output_dir, proc_opts)

    # -- run-level provenance -------------------------------------------------
    prov_options: dict[str, Any] = {
        "adapter": adapter.name,
        "resolution": [options.width, options.height],
        "quality_mode": options.quality_mode,
        "low_memory": options.low_memory,
        "crf": options.crf,
        "scale_filter": scale_filter,
        "filter_threads": effective_filter_threads,
        "filter_complex_threads": effective_fc_threads,
        "decode": options.decode,
        "window_seconds": options.window_seconds,
    }
    if profile is not None:
        prov_options["profile"] = profile.to_dict()
    ingest_run_id, _run_path = emit_ingest_run(
        output_dir=output_dir,
        input_dir=input_dir,
        manifest_path=manifest_for_run,
        options=prov_options,
        encoders_preference=[e.value for e in processor._available_encoders],
    )

    # -- per-clip loop --------------------------------------------------------
    results: list[Path] = []
    plan: dict[str, Any] | None = (
        {
            "tool": "cosmos-ingest",
            "adapter": adapter.name,
            "time": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "options": {
                "resolution": [options.width, options.height],
                "quality_mode": options.quality_mode,
                "low_memory": options.low_memory,
                "crf": options.crf,
            },
            "encoders_preference": [e.value for e in processor._available_encoders],
            "clips": [],
        }
        if options.dry_run
        else None
    )

    for clip in clips_iter:
        clip_result = adapter.validate_clip(clip, input_dir, output_dir)
        if not clip_result.is_valid:
            _log.warning("Skipping invalid clip %s", clip.name)
            continue

        spec = adapter.build_ffmpeg_spec(
            clip,
            clip_result,
            output_dir,
            output_resolution=(options.width, options.height),
            scale_filter=scale_filter,
        )
        output_stem = spec.output_stem or clip.name

        if options.dry_run:
            planned_out = output_dir / f"{output_stem}.mp4"
            if plan is not None:
                plan["clips"].append(
                    {
                        "clip": clip.name,
                        "adapter": adapter.name,
                        "start_time_sec": clip.start_time_sec,
                        "frames": [clip.frame_start, clip.frame_end],
                        "filter_complex": spec.filter_complex,
                        "planned_output": str(planned_out),
                    }
                )
            res = ProcessingResult(
                clip=clip_result.clip,
                output_path=planned_out,
                duration=clip_result.clip.duration,
                frames_processed=clip_result.clip.frame_count,
                success=True,
            )
        else:
            res = processor.process_clip_with_spec(clip_result, spec)

        if res.output_path is None:
            continue

        # Per-clip provenance
        if not options.dry_run and res.success and res.output_path.exists():
            _emit_clip_provenance(
                ingest_run_id,
                clip,
                clip_result,
                spec,
                res,
                options,
                processor,
            )

        results.append(res.output_path)

    if options.dry_run and plan is not None:
        out_json = output_dir / "cosmos_dry_run.json"
        out_json.write_text(json.dumps(plan, indent=2))

    return results


def _emit_clip_provenance(
    ingest_run_id: str,
    clip: ClipDescriptor,
    clip_result: Any,
    spec: Any,
    res: ProcessingResult,
    options: IngestOptions,
    processor: VideoProcessor,
) -> None:
    """Best-effort provenance emission for a single clip."""
    try:
        if clip.end_time_sec is not None:
            end_time_sec = clip.end_time_sec
        else:
            # Adapter flows (for example generic-media) may not know duration
            # at discovery time. Prefer runtime duration and fall back to a
            # probe of the encoded artifact when needed.
            duration_sec = 0.0
            for candidate in (res.duration, clip_result.clip.duration):
                if candidate and candidate > 0:
                    duration_sec = float(candidate)
                    break
            if duration_sec <= 0 and res.output_path is not None:
                probed = ffprobe_video(res.output_path)
                probed_duration = probed.get("duration_sec")
                if isinstance(probed_duration, (int, float)) and probed_duration > 0:
                    duration_sec = float(probed_duration)
            end_time_sec = clip.start_time_sec + duration_sec
        encode_info = {
            "impl": res.used_encoder,
            "filtergraph": spec.filter_complex,
            "crf": options.crf,
        }
        emit_clip_artifact(
            ingest_run_id=ingest_run_id,
            clip_name=clip.name,
            output_path=res.output_path,  # type: ignore[arg-type]
            encode_info=encode_info,
            time_ms=(
                clip.start_time_sec * 1000.0,
                end_time_sec * 1000.0,
            ),
            frames=(clip.frame_start, clip.frame_end),
        )
    except Exception as e:  # noqa: BLE001
        _log.debug("provenance emission failed: %s", e)
