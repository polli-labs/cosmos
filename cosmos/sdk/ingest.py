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

    # -- prepare processor (encoder detection, options) -----------------------
    mode_map = {
        "quality": ProcessingMode.QUALITY,
        "balanced": ProcessingMode.BALANCED,
        "performance": ProcessingMode.PERFORMANCE,
        "low_memory": ProcessingMode.LOW_MEMORY,
        "minimal": ProcessingMode.MINIMAL,
    }
    quality = mode_map.get(options.quality_mode.lower(), ProcessingMode.BALANCED)
    scale_filter = options.scale_filter or (
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
    po.filter_threads = options.filter_threads
    po.filter_complex_threads = options.filter_complex_threads
    po.decode = options.decode
    po.window_seconds = options.window_seconds
    processor = VideoProcessor(output_dir, proc_opts)

    # -- run-level provenance -------------------------------------------------
    ingest_run_id, _run_path = emit_ingest_run(
        output_dir=output_dir,
        input_dir=input_dir,
        manifest_path=manifest,
        options={
            "adapter": adapter.name,
            "resolution": [options.width, options.height],
            "quality_mode": options.quality_mode,
            "low_memory": options.low_memory,
            "crf": options.crf,
            "scale_filter": scale_filter,
            "filter_threads": options.filter_threads,
            "filter_complex_threads": options.filter_complex_threads,
            "decode": options.decode,
            "window_seconds": options.window_seconds,
        },
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
                ((clip.end_time_sec or clip.start_time_sec) + clip_result.clip.duration) * 1000.0,
            ),
            frames=(clip.frame_start, clip.frame_end),
        )
    except Exception as e:  # noqa: BLE001
        _log.debug("provenance emission failed: %s", e)
