# Cosmos Architecture Reference

Detailed module map for the current `cosmos` repo state.

## Package map

- `cosmos/sdk/__init__.py`
  - public exports for ingest/crop.
- `cosmos/sdk/ingest.py`
  - ingest orchestrator and `IngestOptions`.
- `cosmos/sdk/crop.py`
  - crop orchestrator for `CropJob` and `RectCropJob`.
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

- `cosmos/ffmpeg/detect.py`
  - encoder selection, ffmpeg/ffprobe resolution, bootstrap prompt.
- `cosmos/ffmpeg/bootstrap.py`
  - Linux NVENC-capable ffmpeg installer.
- `cosmos/ffmpeg/args.py`
  - ffmpeg arg builders used by crop/ingest paths.
- `cosmos/ffmpeg/presets.py`
  - encoder quality preset tables.

- `cosmos/cli/cosmos_app.py`
  - root CLI app (`ingest`, `crop`, `provenance`, `pipeline`).
- `cosmos/cli/ingest_cli.py`
  - ingest run command + non-interactive flags.
- `cosmos/cli/crop_cli.py`
  - crop run + curated-views command surfaces.
- `cosmos/cli/provenance_cli.py`
  - provenance lookup helpers.

## Provenance artifacts

- Run-level files:
  - `cosmos_ingest_run.v1.json`
  - `cosmos_crop_run.v1.json`
- Artifact-level files:
  - `*.mp4.cosmos_clip.v1.json`
  - `*.mp4.cosmos_view.v1.json`

Join key stability requirement:
- `view.source.sha256 == clip.output.sha256`

## Runtime behavior highlights

- Rect crop now supports normalized and pixel coordinate specs.
- Crop CLI supports `--crop-mode rect` and curated views ingestion.
- Ingest and crop paths honor ffmpeg resolution helpers (env override, cosmos-managed binary, PATH fallback).
- Linux+NVIDIA bootstrap prompt can install NVENC-capable ffmpeg unless suppressed.
