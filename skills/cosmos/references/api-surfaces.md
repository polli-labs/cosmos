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
