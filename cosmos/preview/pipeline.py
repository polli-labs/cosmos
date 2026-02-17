from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cosmos.preview.contracts import ClipArtifacts, ClipPreviewPlan, CropPreviewRun, ResolvedFrame
from cosmos.preview.frames import extract_frame, frame_name_for_time, time_tag
from cosmos.preview.planner import build_view_preview
from cosmos.preview.render import (
    PALETTE,
    compose_contact_sheet,
    render_stacked_overlay,
    render_view_cell,
)
from cosmos.sdk.crop import CropJob, RectCropJob
from cosmos.sdk.provenance import (
    ffmpeg_version,
    ffprobe_video,
    package_version,
    sha256_file,
    system_info,
)

_VIEW_JOB = CropJob | RectCropJob


@dataclass
class PreviewRunResult:
    run_path: Path
    clip_plan_paths: list[Path]
    frame_paths: list[Path]
    sheet_paths: list[Path]
    stacked_paths: list[Path]

    @property
    def outputs(self) -> list[Path]:
        return [self.run_path, *self.clip_plan_paths, *self.sheet_paths, *self.stacked_paths]


@dataclass
class RenderOptions:
    frame_selectors: list[str]
    stack_times_sec: list[float]
    render_max_width: int = 1600
    grid_step_px: int = 400
    show_rulers: bool = True
    alpha: float = 0.25
    dry_run: bool = False
    include_source_sha: bool = False


_SELECTOR_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize(value: str) -> str:
    safe = _SELECTOR_SAFE_RE.sub("_", value.strip())
    return safe.strip("_") or "value"


def _bundle_name(source: Path) -> str:
    digest = hashlib.sha1(str(source).encode("utf-8"), usedforsecurity=False).hexdigest()[:8]  # noqa: S324
    stem = _sanitize(source.stem)
    return f"preview_{stem}_{digest}"


def _resolve_stack_times(
    *, raw_times: list[float], duration_sec: float
) -> tuple[list[float], list[str]]:
    if not raw_times:
        raw_times = [0.0]

    resolved: list[float] = []
    warnings: list[str] = []
    for raw in raw_times:
        clamped = raw
        if clamped < 0:
            clamped = 0.0
        if duration_sec > 0 and clamped > duration_sec:
            clamped = duration_sec
        if clamped != raw:
            warnings.append(f"stack time {raw:.3f}s clamped to {clamped:.3f}s")
        resolved.append(round(clamped, 3))

    deduped = sorted(set(resolved))
    return deduped, warnings


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_clip_plan(
    *,
    source: Path,
    jobs: list[_VIEW_JOB],
    out_dir: Path,
    options: RenderOptions,
) -> tuple[ClipPreviewPlan, Path, list[float]]:
    video = ffprobe_video(source)
    source_w = int(video.get("width_px") or video.get("width") or 0)
    source_h = int(video.get("height_px") or video.get("height") or 0)
    duration = float(video.get("duration_sec") or 0.0)

    if source_w <= 0 or source_h <= 0:
        raise ValueError(f"failed to probe source dimensions for {source}")

    views = [
        build_view_preview(
            job=job,
            index=index,
            source_w=source_w,
            source_h=source_h,
            duration_sec=duration,
            frame_selectors=options.frame_selectors,
        )
        for index, job in enumerate(jobs)
    ]

    stack_times, stack_warnings = _resolve_stack_times(
        raw_times=options.stack_times_sec,
        duration_sec=duration,
    )

    all_frame_times = [frame.time_sec for view in views for frame in view.frame_times]
    all_frame_times.extend(stack_times)
    unique_times = sorted(set(all_frame_times))
    resolved_frames = [ResolvedFrame(selector=time_tag(t), time_sec=t) for t in unique_times]

    bundle_dir = out_dir / _bundle_name(source)
    plan_path = bundle_dir / "preview_plan.v1.json"

    source_payload: dict[str, object] = {"path": str(source)}
    if options.include_source_sha and source.exists() and not options.dry_run:
        source_payload["sha256"] = sha256_file(source)

    artifacts = ClipArtifacts(
        plan=str(plan_path),
        frames=[str(bundle_dir / "frames" / frame_name_for_time(t)) for t in unique_times],
        sheets=[
            str(bundle_dir / "sheets" / f"sheet_frame_{_sanitize(selector)}.png")
            for selector in options.frame_selectors
        ],
        stacked=[str(bundle_dir / "stacked" / f"stacked_{time_tag(t)}.png") for t in stack_times],
    )

    plan = ClipPreviewPlan(
        source=source_payload,
        video=video,
        frame_selectors=options.frame_selectors,
        stack_times_sec=stack_times,
        resolved_frames=resolved_frames,
        views=views,
        warnings=stack_warnings,
        artifacts=artifacts,
    )
    return plan, plan_path, unique_times


def _render_clip(
    *,
    plan: ClipPreviewPlan,
    plan_path: Path,
    options: RenderOptions,
) -> tuple[list[Path], list[Path], list[Path]]:
    source = Path(str(plan.source["path"]))
    bundle_dir = plan_path.parent
    frames_dir = bundle_dir / "frames"
    sheets_dir = bundle_dir / "sheets"
    stacked_dir = bundle_dir / "stacked"
    cells_dir = sheets_dir / "_cells"

    source_w = int(plan.video.get("width_px") or plan.video.get("width") or 0)
    source_h = int(plan.video.get("height_px") or plan.video.get("height") or 0)

    frame_paths: list[Path] = []
    frame_map: dict[float, Path] = {}
    for frame in plan.resolved_frames:
        frame_path = frames_dir / frame_name_for_time(frame.time_sec)
        frame_map[frame.time_sec] = frame_path
        frame_paths.append(frame_path)
        extract_frame(
            input_video=source,
            time_sec=frame.time_sec,
            output_path=frame_path,
            max_width=options.render_max_width,
            dry_run=options.dry_run,
        )

    sheet_paths: list[Path] = []
    for selector in plan.frame_selectors:
        cell_paths: list[Path] = []
        for view_index, view in enumerate(plan.views):
            maybe_frame = next((f for f in view.frame_times if f.selector == selector), None)
            if maybe_frame is None:
                continue
            frame_path = frame_map[maybe_frame.time_sec]
            cell_path = cells_dir / f"{_sanitize(selector)}_{view_index:03d}.png"
            if not options.dry_run:
                color = PALETTE[view_index % len(PALETTE)]
                render_view_cell(
                    frame_path=frame_path,
                    view=view,
                    selector=selector,
                    time_sec=maybe_frame.time_sec,
                    source_w=source_w,
                    source_h=source_h,
                    output_path=cell_path,
                    grid_step_px=options.grid_step_px,
                    show_rulers=options.show_rulers,
                    alpha=options.alpha,
                    color=color,
                )
            cell_paths.append(cell_path)

        sheet_path = sheets_dir / f"sheet_frame_{_sanitize(selector)}.png"
        if not options.dry_run and cell_paths:
            compose_contact_sheet(cell_paths=cell_paths, output_path=sheet_path)
        sheet_paths.append(sheet_path)

    stacked_paths: list[Path] = []
    for stack_time in plan.stack_times_sec:
        frame_path = frame_map[stack_time]
        stacked_path = stacked_dir / f"stacked_{time_tag(stack_time)}.png"
        if not options.dry_run:
            render_stacked_overlay(
                frame_path=frame_path,
                views=plan.views,
                time_sec=stack_time,
                source_w=source_w,
                source_h=source_h,
                output_path=stacked_path,
                grid_step_px=options.grid_step_px,
                show_rulers=options.show_rulers,
            )
        stacked_paths.append(stacked_path)

    plan.artifacts.frames = [str(path) for path in frame_paths]
    plan.artifacts.sheets = [str(path) for path in sheet_paths]
    plan.artifacts.stacked = [str(path) for path in stacked_paths]

    _write_json(plan_path, plan.model_dump())
    return frame_paths, sheet_paths, stacked_paths


def _generate(
    *,
    groups: dict[Path, list[_VIEW_JOB]],
    out_dir: Path,
    options: RenderOptions,
) -> PreviewRunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    plans: list[ClipPreviewPlan] = []
    clip_plan_paths: list[Path] = []
    frame_paths: list[Path] = []
    sheet_paths: list[Path] = []
    stacked_paths: list[Path] = []

    for source, jobs in groups.items():
        plan, plan_path, _times = _build_clip_plan(
            source=source,
            jobs=jobs,
            out_dir=out_dir,
            options=options,
        )
        plans.append(plan)
        clip_plan_paths.append(plan_path)
        clip_frames, clip_sheets, clip_stacked = _render_clip(
            plan=plan,
            plan_path=plan_path,
            options=options,
        )
        frame_paths.extend(clip_frames)
        sheet_paths.extend(clip_sheets)
        stacked_paths.extend(clip_stacked)

    run = CropPreviewRun(
        preview_run_id=f"preview_{uuid.uuid4()}",
        version=package_version("cosmos"),
        time=_now_iso(),
        output_dir=str(out_dir),
        frame_selectors=options.frame_selectors,
        stack_times_sec=options.stack_times_sec,
        render_defaults={
            "render_max_width": options.render_max_width,
            "grid_step_px": options.grid_step_px,
            "show_rulers": options.show_rulers,
            "alpha": options.alpha,
        },
        ffmpeg=ffmpeg_version(),
        system=system_info(),
        clips=plans,
    )
    run_path = out_dir / "cosmos_crop_preview_run.v1.json"
    _write_json(run_path, run.model_dump())

    return PreviewRunResult(
        run_path=run_path,
        clip_plan_paths=clip_plan_paths,
        frame_paths=frame_paths,
        sheet_paths=sheet_paths,
        stacked_paths=stacked_paths,
    )


def generate_preview_for_jobs(
    *,
    input_videos: list[Path],
    jobs: list[CropJob] | list[RectCropJob],
    out_dir: Path,
    options: RenderOptions,
) -> PreviewRunResult:
    groups: dict[Path, list[_VIEW_JOB]] = {}
    for video in input_videos:
        groups[Path(video)] = [job for job in jobs]
    if not groups:
        raise ValueError("at least one input video is required for preview")
    return _generate(groups=groups, out_dir=out_dir, options=options)


def generate_preview_for_curated_pairs(
    *,
    pairs: list[tuple[Path, RectCropJob]],
    out_dir: Path,
    options: RenderOptions,
) -> PreviewRunResult:
    groups: dict[Path, list[_VIEW_JOB]] = {}
    for source, job in pairs:
        key = Path(source)
        if key not in groups:
            groups[key] = []
        groups[key].append(job)
    if not groups:
        raise ValueError("curated preview requires at least one view")
    return _generate(groups=groups, out_dir=out_dir, options=options)
