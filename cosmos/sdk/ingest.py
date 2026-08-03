from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from cosmos.ingest.adapter import ClipDescriptor, FfmpegInputSpec
from cosmos.ingest.adapters import resolve_adapter
from cosmos.ingest.preflight import preflight
from cosmos.ingest.processor import (
    ProcessingMode,
    ProcessingOptions,
    ProcessingResult,
    VideoProcessor,
)
from cosmos.ingest.validation import ValidationIssue, ValidationLevel
from cosmos.sdk.dry_run import (
    build_dry_run_plan,
    command_declaration,
    input_declaration,
    output_declaration,
    write_dry_run_plan,
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
    quality_mode: str = "balanced"  # speed|balanced|quality
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


QUALITY_MODES: dict[str, ProcessingMode] = {
    "speed": ProcessingMode.PERFORMANCE,
    "balanced": ProcessingMode.BALANCED,
    "quality": ProcessingMode.QUALITY,
}
SCALE_FILTERS: frozenset[str] = frozenset({"lanczos", "bicubic", "spline36", "bilinear"})
DECODE_MODES: frozenset[str] = frozenset({"auto", "hw", "sw"})


class IngestSystemPreflightError(RuntimeError):
    """Adapter system preflight found fatal issues before ingest could run."""


def _normalized_option_value(
    field: str, value: str | None, accepted: set[str] | frozenset[str]
) -> str:
    if value is None:
        raise ValueError(f"Internal error: {field} cannot be None")
    normalized = value.strip().lower()
    if normalized not in accepted:
        accepted_values = ", ".join(sorted(accepted))
        raise ValueError(
            f"Invalid ingest option {field}={value!r}. Accepted values: {accepted_values}"
        )
    return normalized


def _format_preflight_issues(adapter_name: str, issues: list[ValidationIssue]) -> str:
    lines = [f"Ingest adapter {adapter_name!r} system preflight failed:"]
    for issue in issues:
        parts = [f"- {issue.level.value}: {issue.message}"]
        if issue.context:
            parts.append(f"context: {issue.context}")
        if issue.help_text:
            parts.append(f"help: {issue.help_text}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _safe_plan_name(value: str) -> str:
    keep = [ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value]
    return "".join(keep).strip("._") or "clip"


def _persist_dry_run_temp_files(
    spec: FfmpegInputSpec,
    output_dir: Path,
    *,
    clip_name: str,
    argv: list[str],
) -> tuple[list[str], list[dict[str, object]], list[Path]]:
    """Copy adapter temp files into the plan tree and rewrite argv references."""
    if not spec.temp_files:
        return argv, [], []

    plan_dir = output_dir / ".cosmos-dry-run" / "ingest"
    plan_dir.mkdir(parents=True, exist_ok=True)
    rewritten = list(argv)
    inputs: list[dict[str, object]] = []
    metadata_writes: list[Path] = []
    for index, temp_file in enumerate(spec.temp_files):
        temp_path = Path(temp_file)
        if not temp_path.exists():
            continue
        suffix = temp_path.suffix or ".txt"
        plan_path = plan_dir / f"{_safe_plan_name(clip_name)}-{index:02d}{suffix}"
        shutil.copy2(temp_path, plan_path)
        rewritten = [str(plan_path) if arg == str(temp_path) else arg for arg in rewritten]
        inputs.append(input_declaration(plan_path, kind="metadata", stage="ingest"))
        metadata_writes.append(plan_path)
    return rewritten, inputs, metadata_writes


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
    quality_mode = _normalized_option_value(
        "quality_mode",
        options.quality_mode,
        set(QUALITY_MODES),
    )
    decode = _normalized_option_value("decode", options.decode, DECODE_MODES)
    scale_filter_override = (
        _normalized_option_value("scale_filter", options.scale_filter, SCALE_FILTERS)
        if options.scale_filter is not None
        else None
    )

    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory not found: {input_dir}")
    ensure_dir(output_dir)
    preflight(input_dir)

    # -- resolve determinism profile ------------------------------------------
    from cosmos.sdk.profiles import resolve_profile

    profile = resolve_profile(options.profile)

    # -- resolve adapter ------------------------------------------------------
    adapter = resolve_adapter(input_dir, adapter_name=options.adapter)
    _log.info("Using ingest adapter: %s", adapter.name)

    # -- system pre-checks ----------------------------------------------------
    system_issues = adapter.validate_system(output_dir)
    fatal_issues = [issue for issue in system_issues if issue.level == ValidationLevel.ERROR]
    if fatal_issues:
        raise IngestSystemPreflightError(_format_preflight_issues(adapter.name, system_issues))

    # -- discover clips -------------------------------------------------------
    all_clips = adapter.discover_clips(input_dir)
    if options.clips:
        wanted = {c.upper() for c in options.clips}
        clips_iter = [c for c in all_clips if c.name.upper() in wanted]
    else:
        clips_iter = all_clips

    no_clip_validation: list[dict[str, object]] = []
    if not clips_iter:
        _log.warning("No clips discovered by adapter %r in %s", adapter.name, input_dir)
        if not options.dry_run:
            return []
        no_clip_validation.append(
            {
                "level": "warning",
                "stage": "ingest",
                "message": "No clips matched discovery/filter criteria.",
                "requested_clips": options.clips or [],
                "discovered_count": len(all_clips),
            }
        )

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

    # Apply profile defaults where the caller did not set an explicit value.
    effective_filter_threads = options.filter_threads
    effective_fc_threads = options.filter_complex_threads
    effective_scale_filter = scale_filter_override
    if profile is not None:
        if effective_filter_threads is None and profile.threads is not None:
            effective_filter_threads = profile.threads
        if effective_fc_threads is None and profile.threads is not None:
            effective_fc_threads = profile.threads
        if effective_scale_filter is None and profile.scale_filter is not None:
            effective_scale_filter = _normalized_option_value(
                "scale_filter",
                profile.scale_filter,
                SCALE_FILTERS,
            )

    # -- prepare processor (encoder detection, options) -----------------------
    quality = QUALITY_MODES[quality_mode]
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
    po.decode = decode
    po.window_seconds = options.window_seconds
    po.bitexact = profile.bitexact if profile else False
    po.pinned_encoder = profile.pinned_encoder if profile else None
    processor = VideoProcessor(output_dir, proc_opts)

    # -- run-level provenance -------------------------------------------------
    prov_options: dict[str, Any] = {
        "adapter": adapter.name,
        "resolution": [options.width, options.height],
        "quality_mode": quality_mode,
        "low_memory": options.low_memory,
        "crf": options.crf,
        "scale_filter": scale_filter,
        "filter_threads": effective_filter_threads,
        "filter_complex_threads": effective_fc_threads,
        "decode": decode,
        "window_seconds": options.window_seconds,
    }
    if profile is not None:
        prov_options["profile"] = profile.to_dict()
    ingest_run_id, run_path = emit_ingest_run(
        output_dir=output_dir,
        input_dir=input_dir,
        manifest_path=manifest_for_run,
        options=prov_options,
        encoders_preference=[e.value for e in processor._available_encoders],
    )

    # -- per-clip loop --------------------------------------------------------
    results: list[Path] = []
    dry_run_inputs: list[dict[str, object]] = [
        input_declaration(input_dir, kind="directory", stage="ingest")
    ]
    dry_run_outputs: list[dict[str, object]] = []
    dry_run_commands: list[dict[str, object]] = []
    dry_run_validation: list[dict[str, object]] = list(no_clip_validation)
    dry_run_metadata_writes: list[Path] = []
    legacy_clip_entries: list[dict[str, object]] = []

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
        if options.dry_run:
            try:
                planned_out, argv = processor.build_command_for_spec(clip_result, spec)
                argv, persisted_inputs, persisted_metadata_writes = _persist_dry_run_temp_files(
                    spec,
                    output_dir,
                    clip_name=clip.name,
                    argv=argv,
                )
                dry_run_inputs.extend(persisted_inputs)
                dry_run_metadata_writes.extend(persisted_metadata_writes)
                dry_run_outputs.append(
                    output_declaration(
                        planned_out,
                        kind="video",
                        stage="ingest",
                        exists=False,
                    )
                )
                dry_run_commands.append(
                    command_declaration(
                        stage="ingest",
                        name=clip.name,
                        argv=argv,
                        inputs=[input_dir],
                        outputs=[planned_out],
                    )
                )
                legacy_clip_entries.append(
                    {
                        "clip": clip.name,
                        "adapter": adapter.name,
                        "start_time_sec": clip.start_time_sec,
                        "frames": [clip.frame_start, clip.frame_end],
                        "filter_complex": spec.filter_complex,
                        "planned_output": str(planned_out),
                        "command": argv,
                    }
                )
            finally:
                for temp_file in spec.temp_files:
                    try:
                        Path(temp_file).unlink(missing_ok=True)
                    except OSError as exc:
                        _log.debug("Failed to cleanup dry-run temp file %s: %s", temp_file, exc)
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

    if options.dry_run:
        out_json = output_dir / "cosmos_ingest_dry_run.v1.json"
        plan = build_dry_run_plan(
            command="cosmos ingest run",
            inputs=dry_run_inputs,
            outputs=dry_run_outputs,
            commands=dry_run_commands,
            metadata_writes=[run_path, out_json, *dry_run_metadata_writes],
            validation=dry_run_validation,
            extra={
                "tool": "cosmos-ingest",
                "adapter": adapter.name,
                "time": datetime.now(timezone.utc).isoformat(),
                "input_dir": str(input_dir),
                "output_dir": str(output_dir),
                "options": {
                    "resolution": [options.width, options.height],
                    "quality_mode": quality_mode,
                    "low_memory": options.low_memory,
                    "crf": options.crf,
                    "scale_filter": scale_filter,
                    "filter_threads": effective_filter_threads,
                    "filter_complex_threads": effective_fc_threads,
                    "decode": decode,
                    "window_seconds": options.window_seconds,
                },
                "encoders_preference": [e.value for e in processor._available_encoders],
                "clips": legacy_clip_entries,
            },
        )
        write_dry_run_plan(out_json, plan)

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
    """Emit provenance for a successfully written clip artifact."""
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
            if isinstance(probed_duration, int | float) and probed_duration > 0:
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
