# Cosmos API Surfaces

Current SDK and CLI contracts to preserve when changing interfaces.

## SDK surfaces

### Ingest

- `ingest(input_dir, output_dir, *, manifest, options) -> list[Path]`
- `IngestOptions` controls quality mode, resolution, dry-run, clip filtering, decoder preference, filter-thread knobs, and source adapter selection (`adapter` field).
- Adapter contract: `IngestAdapter` Protocol in `cosmos.ingest.adapter` — defines `detect()`, `discover_clips()`, `validate_clip()`, `build_ffmpeg_spec()`, `validate_system()`.
- Built-in adapters: `cosm` (COSM C360), `generic-media` (flat video directory). Auto-detected by default; explicit via `IngestOptions.adapter` or CLI `--adapter`.

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

### Optimize

- `optimize(input_videos, out_dir, *, options) -> list[Path]`
- `OptimizeOptions` supports:
  - `mode`: `auto|remux|transcode`
  - transform flags: `target_height`, `fps`, `crf`, optional forced `encoder`
  - safety flags: `force`, `dry_run`, `faststart`, `suffix`
  - `profile`: determinism profile (`strict|balanced|throughput`) — controls encoder pinning, thread count, and bitexact flags
- Optimize outputs emit:
  - run-level `cosmos_optimize_run.v1.json`
  - per-output `*.mp4.cosmos_optimized.v1.json` (non-dry-run)
  - dry-run plan `cosmos_optimize_dry_run.json`
- Encoder behavior:
  - auto-selected hardware encoders are runtime-probed and degrade to `libx264` when unavailable.
  - explicitly forced encoders are treated as strict and fail fast on ffmpeg errors.

### Lineage

- `build_index(*dirs) -> LineageIndex`: Scan directories for provenance sidecars and build a DAG.
- `LineageIndex.upstream(sha256) -> list[Node]`: Transitive ancestors.
- `LineageIndex.downstream(sha256) -> list[Node]`: Transitive descendants.
- `LineageIndex.chain(sha256) -> list[Node]`: Full lineage (upstream + self + downstream).
- `LineageIndex.tree(sha256) -> dict`: Nested source hierarchy.
- `LineageIndex.write(path) -> Path`: Serialize index to JSON.
- `LineageIndex.to_dict() -> dict`: Serialize to dict with `cosmos-lineage-index-v1` schema.

### Provenance

- Emitters:
  - `emit_ingest_run`, `emit_clip_artifact`, `emit_crop_run`, `emit_crop_view`, `emit_optimize_run`, `emit_optimized_artifact`
- Lookup helpers:
  - `find_clip_for_file`, `find_view_for_file`, `views_for_clip`, `map_artifacts_by_sha`

## CLI surfaces

### Root app

- `cosmos ingest ...` (supports `--adapter` for source layout selection)
- `cosmos crop ...`
- `cosmos optimize ...`
- `cosmos provenance ...`
- `cosmos lineage ...`
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
  - key flags: `--frame`, `--stack-time`, `--render-max-width`, `--grid-step-px`, `--show-rulers`, `--show-crosshair`, `--alpha`
- `cosmos crop curated-views-preview`
  - curated-spec preview renderer grouped by source clip
  - key flags mirror `crop preview` and include `--spec --source-root --out [--clip-pattern]`

### Optimize commands

- `cosmos optimize run`
  - modes: `--mode auto|remux|transcode`
  - transforms: `--target-height`, `--fps`, `--crf`, `--encoder`
  - determinism: `--profile strict|balanced|throughput`
  - safety/io: `--faststart`, `--suffix`, `--force`, `--yes`, `--dry-run`, `--json|--plain`

### Lineage commands

- `cosmos lineage build <dirs...> [--output FILE] [--json|--plain]`
  - Scans directories for provenance sidecars and builds a lineage index.
- `cosmos lineage upstream <identifier> [--in <dir>...] [--json|--plain]`
  - Shows all transitive ancestors of the artifact.
- `cosmos lineage downstream <identifier> [--in <dir>...] [--json|--plain]`
  - Shows all transitive derivatives of the artifact.
- `cosmos lineage chain <identifier> [--in <dir>...] [--json|--plain]`
  - Full chain: upstream + self + downstream.
- `cosmos lineage tree <identifier> [--in <dir>...] [--json|--plain]`
  - Nested upstream source hierarchy.
- Identifiers accept full sha256, sha256 prefix, or artifact ID.

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
