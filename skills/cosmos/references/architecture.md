# Cosmos Architecture Reference

Detailed module map for the current `cosmos` repo state.

## Package map

- `cosmos/sdk/__init__.py`
  - public exports for ingest/crop/preview.
- `cosmos/sdk/ingest.py`
  - ingest orchestrator and `IngestOptions`.
- `cosmos/sdk/crop.py`
  - crop orchestrator for `CropJob` and `RectCropJob`.
- `cosmos/sdk/optimize.py`
  - optimize orchestrator and `OptimizeOptions` for remux/transcode workflows.
- `cosmos/sdk/preview.py`
  - preview orchestrator wrappers and `RenderOptions`.
- `cosmos/sdk/provenance.py`
  - emitters/resolvers for run/artifact provenance.

- `cosmos/ingest/manifest.py`
  - COSM manifest parsing and clip metadata.
- `cosmos/ingest/validation.py`
  - system + segment validation.
- `cosmos/ingest/processor.py`
  - ffmpeg command generation and encode execution.

- `cosmos/crop/squarecrop.py`
  - square crop filter planning/execution.
- `cosmos/crop/rectcrop.py`
  - rectangular crop filter planning/execution.
- `cosmos/crop/jobs.py`
  - jobs parser for square and rect modes.
- `cosmos/crop/curated_views.py`
  - curated-view-spec parser and source clip mapping.

- `cosmos/preview/contracts.py`
  - preview run/plan Pydantic contracts for bundle artifacts.
- `cosmos/preview/selectors.py`
  - frame selector parsing and selector-to-time resolution.
- `cosmos/preview/planner.py`
  - deterministic rect/square preview geometry and warnings.
- `cosmos/preview/frames.py`
  - ffmpeg frame extraction builder/executor.
- `cosmos/preview/render.py`
  - static overlay rendering for per-view contact cells and stacked overlays.
- `cosmos/preview/pipeline.py`
  - end-to-end preview pipeline orchestration and artifact writing.

- `cosmos/ffmpeg/detect.py`
  - encoder selection, ffmpeg/ffprobe resolution, bootstrap prompt.
- `cosmos/ffmpeg/bootstrap.py`
  - Linux NVENC-capable ffmpeg installer.
- `cosmos/ffmpeg/args.py`
  - ffmpeg arg builders used by crop/optimize/ingest paths.
- `cosmos/ffmpeg/presets.py`
  - encoder quality preset tables.

- `cosmos/cli/cosmos_app.py`
  - root CLI app (`ingest`, `crop`, `optimize`, `provenance`, `pipeline`).
- `cosmos/cli/ingest_cli.py`
  - ingest run command + non-interactive flags.
- `cosmos/cli/crop_cli.py`
  - crop run + curated-views + preview command surfaces.
- `cosmos/cli/optimize_cli.py`
  - optimize run command (`auto|remux|transcode`) with machine-output contracts.
- `cosmos/cli/provenance_cli.py`
  - provenance lookup helpers.

## Provenance artifacts

- Run-level files:
  - `cosmos_ingest_run.v1.json`
  - `cosmos_crop_run.v1.json`
  - `cosmos_optimize_run.v1.json`
  - `cosmos_crop_preview_run.v1.json`
- Artifact-level files:
  - `*.mp4.cosmos_clip.v1.json`
  - `*.mp4.cosmos_view.v1.json`
  - `*.mp4.cosmos_optimized.v1.json`
  - `preview_<clip>_<hash>/preview_plan.v1.json`

Join key stability requirement:
- `view.source.sha256 == clip.output.sha256`

## Runtime behavior highlights

- Rect crop now supports normalized and pixel coordinate specs.
- Crop CLI supports `--crop-mode rect` and curated views ingestion.
- Crop preview now supports contact sheets + stacked overlays with frame selectors and a GUI-ready preview-plan contract.
- Ingest and crop paths honor ffmpeg resolution helpers (env override, cosmos-managed binary, PATH fallback).
- Linux+NVIDIA bootstrap prompt can install NVENC-capable ffmpeg unless suppressed.
