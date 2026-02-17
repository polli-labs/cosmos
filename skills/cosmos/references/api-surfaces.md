# Cosmos API Surfaces

Current SDK and CLI contracts to preserve when changing interfaces.

## SDK surfaces

### Ingest

- `ingest(input_dir, output_dir, *, manifest, options) -> list[Path]`
- `IngestOptions` controls quality mode, resolution, dry-run, clip filtering, decoder preference, and filter-thread knobs.

### Crop

- `crop(input_videos, jobs, out_dir, *, ffmpeg_opts) -> list[Path]`
- Job types:
  - `CropJob` (square mode)
  - `RectCropJob` (rect mode, includes `view_id`, `annotations`)
- `crop()` requires homogeneous job lists (all square or all rect).

### Preview

- `preview(input_videos, jobs, out_dir, *, options) -> PreviewRunResult`
- `preview_curated_views(pairs, out_dir, *, options) -> PreviewRunResult`
- `RenderOptions` controls keyframe selectors, stacked overlay times, render scale, diagnostics, and dry-run behavior.
- Preview outputs are bundle-oriented:
  - run-level `cosmos_crop_preview_run.v1.json`
  - per-clip `preview_plan.v1.json` + image artifacts (`frames/`, `sheets/`, `stacked/`)

### Provenance

- Emitters:
  - `emit_ingest_run`, `emit_clip_artifact`, `emit_crop_run`, `emit_crop_view`
- Lookup helpers:
  - `find_clip_for_file`, `find_view_for_file`, `views_for_clip`, `map_artifacts_by_sha`

## CLI surfaces

### Root app

- `cosmos ingest ...`
- `cosmos crop ...`
- `cosmos provenance ...`
- `cosmos pipeline ...` (legacy convenience path)

### Crop commands

- `cosmos crop run`
  - supports square defaults plus rect mode flags:
    - `--crop-mode {square|rect}`
    - `--x0 --y0 --width --height [--px]`
- `cosmos crop curated-views`
  - `--spec --source-root --out [--clip-pattern]`
- `cosmos crop preview`
  - jobs-based preview renderer (single clip or multi-clip)
  - key flags: `--frame`, `--stack-time`, `--render-max-width`, `--grid-step-px`, `--show-rulers`, `--alpha`
- `cosmos crop curated-views-preview`
  - curated-spec preview renderer grouped by source clip
  - key flags mirror `crop preview` and include `--spec --source-root --out [--clip-pattern]`

### Non-interactive safety

- `--yes` to suppress prompts.
- `--skip-ffmpeg-check` to suppress bootstrap prompt.
- `--dry-run` must avoid side-effectful encode execution.

## Exit-code policy (target contract for redesign)

- `0`: success
- `2`: invalid usage / argument validation failure
- `3`: input validation failure (missing clips/specs/manifests)
- `4`: ffmpeg preflight/bootstrap resolution failure
- `5`: processing failure (ffmpeg run error after preflight)

Current CLI does not fully standardize this map yet; redesign work should align behavior to this contract.
