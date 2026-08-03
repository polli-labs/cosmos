# Cosmos Architecture Reference

Detailed module map for the current `cosmos` repo state.

## Package map

- `cosmos/sdk/__init__.py`
  - public exports for video probe/decode, ingest/crop/preview/optimize, and determinism
    profile helpers.
- `cosmos/sdk/video.py`
  - stable SDK re-export surface for typed video metadata/timeline/decode helpers.
- `cosmos/sdk/ingest.py`
  - ingest orchestrator and `IngestOptions`. Uses adapter contract for source-layout-specific logic.
- `cosmos/sdk/crop.py`
  - crop orchestrator for `CropJob` and `RectCropJob`.
- `cosmos/sdk/optimize.py`
  - optimize orchestrator and `OptimizeOptions` for remux/transcode workflows.
- `cosmos/sdk/preview.py`
  - preview orchestrator wrappers and `RenderOptions`.
- `cosmos/sdk/profiles.py`
  - determinism profile model (`strict|balanced|throughput`) and precedence resolver.
- `cosmos/sdk/provenance.py`
  - emitters/resolvers for run/artifact provenance.
- `cosmos/sdk/lineage.py`
  - lineage index builder and graph traversal (DAG over provenance sidecars).

- `cosmos/video/types.py`
  - `VideoProbe`, `VideoFrameTimeline`, `RgbFrame`, and video-specific error classes.
- `cosmos/video/probe.py`
  - ffprobe JSON-backed first-video-stream metadata probing.
- `cosmos/video/timeline.py`
  - exact first-video-stream time-base parsing and strictly increasing decoded-frame PTS
    identity extraction through the shared ffprobe resolver and optional video subprocess
    timeout.
- `cosmos/video/decode.py`
  - public video decode validation, backend selection, and `RgbFrame` assembly.
- `cosmos/video/backends/`
  - internal decode backend protocol plus concrete `ffmpeg-cli`, optional PyAV,
    and optional TorchCodec implementations for raw `rgb24` byte extraction.

- `cosmos/ingest/adapter.py`
  - `IngestAdapter` Protocol, `ClipDescriptor`, `FfmpegInputSpec` — adapter contract.
- `cosmos/ingest/adapters/__init__.py`
  - adapter registry and `resolve_adapter()` auto-detection.
- `cosmos/ingest/adapters/cosm.py`
  - COSM C360 adapter: manifest parsing, segment validation, quad-tile filter graph.
- `cosmos/ingest/adapters/generic_media.py`
  - generic-media adapter: flat video directory, per-file clips, scale-only filter.
- `cosmos/ingest/manifest.py`
  - COSM manifest parsing and clip metadata (used by COSM adapter).
- `cosmos/ingest/validation.py`
  - system + segment validation (used by COSM adapter).
- `cosmos/ingest/processor.py`
  - ffmpeg command generation and encode execution. `process_clip_with_spec()` accepts adapter-provided `FfmpegInputSpec`.

- `cosmos/crop/squarecrop.py`
  - square crop filter planning/execution.
- `cosmos/crop/rectcrop.py`
  - rectangular crop filter planning/execution.
- `cosmos/crop/jobs.py`
  - jobs parser for square and rect modes.
- `cosmos/crop/curated_views.py`
  - curated-view-spec parser and source clip mapping.

- `cosmos/preview/contracts.py`
  - preview run/plan Pydantic contracts for bundle artifacts; `PreviewRect`
    preserves its eight-field v1 model and offers a non-serialized, optional
    Typus `BBoxXYWHNorm` view.
- `cosmos/preview/selectors.py`
  - frame selector parsing and selector-to-time resolution.
- `cosmos/preview/planner.py`
  - deterministic rect/square preview geometry and warnings; clamp and
    forced-even ffmpeg pixel math remains the authority behind normalized and
    Typus projections.
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
  - root CLI app (`process`, `ingest`, `crop`, `optimize`, `provenance`, `lineage`).
- `cosmos/cli/ingest_cli.py`
  - ingest run command + non-interactive flags.
- `cosmos/cli/crop_cli.py`
  - crop run + curated-views + preview command surfaces.
- `cosmos/cli/optimize_cli.py`
  - optimize run command (`auto|remux|transcode`) with machine-output contracts.
- `cosmos/cli/provenance_cli.py`
  - provenance lookup helpers.
- `cosmos/cli/lineage_cli.py`
  - lineage index build/query commands for upstream/downstream/chain/tree traversal.

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

- Root workflow command is `cosmos process`; legacy `cosmos pipeline` is retired.
- Rect crop now supports normalized and pixel coordinate specs.
- Crop CLI supports `--crop-mode rect` and curated views ingestion.
- Crop preview now supports contact sheets + stacked overlays with frame selectors and a GUI-ready preview-plan contract.
- Video probe/timeline/decode now has a typed SDK substrate (`cosmos.sdk.video`) for
  downstream consumers that need metadata, exact decoded-frame PTS identities, and RGB
  frames without depending on Decord or image-array return types.
- `probe_video_timeline()` consumes ffprobe `-show_frames` output in emitted decoded-frame
  order, accepts only literal frame `pts`, and rejects missing, estimated-only,
  non-integral, duplicate, or nonmonotonic identity sequences.
- Metadata probes, exact timeline probes, packet timestamp lookups, and FFmpeg RGB extraction
  share the call-time `COSMOS_VIDEO_FFMPEG_TIMEOUT` contract and stable typed error wrapping.
- The default video decode backend remains FFmpeg CLI for stable system-FFmpeg bytes.
  Optional PyAV is lazy-imported behind `polli-cosmos[video-av]` and selected only via
  `COSMOS_VIDEO_BACKEND=pyav`, or by platform-aware `auto` on macOS with FFmpeg CLI
  fallback. Linux `auto` keeps FFmpeg CLI unless PyAV is forced.
- Optional TorchCodec is lazy-imported behind `polli-cosmos[video-torchcodec]` and selected
  only via `COSMOS_VIDEO_BACKEND=torchcodec`. It decodes CPU tensors with
  `dimension_order=NHWC` and converts them back to Cosmos' public `RgbFrame.rgb24`
  byte contract.
- Ingest and crop paths honor ffmpeg resolution helpers (env override, cosmos-managed binary, PATH fallback).
- Linux+NVIDIA bootstrap prompt can install NVENC-capable ffmpeg unless suppressed.
- Ingest uses an adapter contract (`IngestAdapter` Protocol) for source-layout-specific logic. Built-in adapters: `cosm` (COSM C360 quad-tile) and `generic-media` (flat video directory). Auto-detected by default; overridable via `--adapter` CLI flag or `IngestOptions.adapter` SDK parameter.
- Determinism profiles apply across ingest/crop/optimize with precedence `--profile` > `COSMOS_PROFILE` > defaults, and selected profile is captured in run-level provenance.
