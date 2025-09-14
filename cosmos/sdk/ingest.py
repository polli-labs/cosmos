from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from cosmos.ingest.manifest import ManifestParser, find_manifest
from cosmos.ingest.preflight import preflight
from cosmos.ingest.processor import (
    ProcessingMode,
    ProcessingOptions,
    ProcessingResult,
    VideoProcessor,
)
from cosmos.ingest.validation import InputValidator
from cosmos.sdk.provenance import (
    emit_clip_artifact,
    emit_ingest_run,
)
from cosmos.utils.io import ensure_dir, find_videos


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


def ingest(  # noqa: C901
    input_dir: Path,
    output_dir: Path,
    *,
    manifest: Path | None,
    options: IngestOptions,
) -> list[Path]:  # noqa: C901
    """Return list of generated MP4 paths using the imported pipeline.

    Fallback: if no manifest is found, simulate simple outputs from discovered mp4s.
    """
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory not found: {input_dir}")
    ensure_dir(output_dir)
    preflight(input_dir)

    # Try to find a manifest; if none, fallback to discovered videos
    manifest_path = manifest or find_manifest(input_dir)
    results: list[Path] = []
    if manifest_path is None:
        for i, _video in enumerate(find_videos(input_dir)):
            out = output_dir / f"ingest_{i:03d}.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"")
            results.append(out)
        return results

    parser = ManifestParser(manifest_path)
    validator = InputValidator(input_dir, output_dir, parser)
    _ = validator.validate_system()  # Could be surfaced to caller if needed
    mode_map = {
        "quality": ProcessingMode.QUALITY,
        "balanced": ProcessingMode.BALANCED,
        "performance": ProcessingMode.PERFORMANCE,
        "low_memory": ProcessingMode.LOW_MEMORY,
        "minimal": ProcessingMode.MINIMAL,
    }
    quality = mode_map.get(options.quality_mode.lower(), ProcessingMode.BALANCED)
    # Default scale filter by mode if not explicitly provided
    scale_filter = options.scale_filter or ("lanczos" if quality == ProcessingMode.QUALITY else "bicubic")
    proc_opts = ProcessingOptions(
        output_resolution=(options.width, options.height),
        quality_mode=quality,
        low_memory=options.low_memory,
        crf=options.crf,
    )
    # Attach optional attributes to avoid breaking older ProcessingOptions
    po = cast(Any, proc_opts)
    po.scale_filter = scale_filter
    po.filter_threads = options.filter_threads
    po.filter_complex_threads = options.filter_complex_threads
    po.decode = options.decode
    po.window_seconds = options.window_seconds
    processor = VideoProcessor(output_dir, proc_opts)

    # Emit run-level provenance (after processor init so we can record encoder prefs)
    ingest_run_id, _run_path = emit_ingest_run(
        output_dir=output_dir,
        input_dir=input_dir,
        manifest_path=manifest_path,
        options={
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

    # Validate each clip and process
    plan: dict[str, Any] | None = {
        "tool": "cosmos-ingest",
        "time": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "options": {
            "resolution": [options.width, options.height],
            "quality_mode": options.quality_mode,
            "low_memory": options.low_memory,
            "crf": options.crf,
        },
        "encoders_preference": [e.value for e in processor._available_encoders],
        "filter_complex": processor._build_filter_complex(),
        "clips": [],
    } if options.dry_run else None
    all_clips = parser.get_clips()
    if options.clips:
        wanted = {c.upper() for c in options.clips}
        clips_iter = [c for c in all_clips if c.name.upper() in wanted]
    else:
        clips_iter = all_clips
    for clip in clips_iter:
        clip_result = validator.validate_clip(clip)
        if not clip_result.is_valid:
            continue
        if options.dry_run:
            planned_out = output_dir / f"{clip.name}.mp4"
            if plan is not None:
                plan["clips"].append({
                    "clip": clip.name,
                    "start_pos": clip.start_pos.to_string(),
                    "frames": [clip.start_idx, clip.end_idx],
                    "duration": clip.duration,
                    "planned_output": str(planned_out),
                })
            res = ProcessingResult(
                clip=clip,
                output_path=planned_out,
                duration=clip.duration,
                frames_processed=clip.frame_count,
                success=True,
            )
        else:
            res = processor.process_clip(clip_result)
        if res.output_path is None:
            continue
        # Emit per-clip provenance on successful encode
        if not options.dry_run and res.success and res.output_path.exists():
            try:
                encode_info = {"impl": res.used_encoder, "filtergraph": processor._build_filter_complex(), "crf": options.crf}
                emit_clip_artifact(
                    ingest_run_id=ingest_run_id,
                    clip_name=clip.name,
                    output_path=res.output_path,
                    encode_info=encode_info,
                    time_ms=(clip.start_pos.to_seconds() * 1000.0, (clip.start_pos.to_seconds() + clip.duration) * 1000.0),
                    frames=(clip.start_idx, clip.end_idx),
                )
            except Exception as e:
                # Non-fatal if provenance emission fails
                import logging

                logging.getLogger(__name__).debug("provenance emission failed: %s", e)
        results.append(res.output_path)
    if options.dry_run and plan is not None:
        out_json = output_dir / "cosmos_dry_run.json"
        out_json.write_text(json.dumps(plan, indent=2))
    return results
