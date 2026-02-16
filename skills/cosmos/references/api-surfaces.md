# Cosmos API Surfaces

Current SDK and CLI contracts to preserve when changing interfaces.

## SDK surfaces

### Ingest

- `ingest(input_dir, output_dir, *, manifest, options) -> list[Path]`
- `IngestOptions` controls quality mode, resolution, dry-run, clip filtering, decoder preference, and filter-thread knobs.

### Crop

- `crop(input_videos, jobs, out_dir, *, ffmpeg_opts) -> list[Path]`
- Job type:
  - `CropJob` (square mode; supports `center_*` or margin-relative `offset_*`, optional `start`/`end` trim)
- Trim contract:
  - when both `start` and `end` are set, ffmpeg args must encode duration as `-t (end-start)` (not absolute `-to`).

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
  - supports square crop flags:
    - `--jobs-file`
    - `--size --offset-x --offset-y --center-x --center-y`
    - `--trim-start --trim-end`
    - `--prefer-hevc-hw`

### Non-interactive safety

- `--yes` to suppress prompts.
- `--dry-run` must avoid side-effectful encode execution.

## Exit-code policy (target contract for redesign)

- `0`: success
- `2`: invalid usage / argument validation failure
- `3`: input validation failure (missing clips/specs/manifests)
- `4`: ffmpeg preflight/bootstrap resolution failure
- `5`: processing failure (ffmpeg run error after preflight)

Current CLI does not fully standardize this map yet; redesign work should align behavior to this contract.
