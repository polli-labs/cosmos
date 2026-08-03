# Cosmos API Surfaces

Current SDK and CLI contracts to preserve when changing interfaces.

## SDK surfaces

### Video

- `probe_video(path) -> VideoProbe`
- `probe_video_timeline(path) -> VideoFrameTimeline`
- `extract_frames_at_indices(path, indices, *, probe=None) -> list[RgbFrame]`
- `extract_frames_at_times(path, times_seconds, *, probe=None) -> list[RgbFrame]`
- `VideoProbe` exposes source path, dimensions, duration/fps/frame count when known,
  codec names, and format name.
- `VideoFrameTimeline` is immutable and exposes source path, the first video stream's exact
  `time_base_numerator` / `time_base_denominator`, and `pts_ticks: tuple[int, ...]` in
  ffprobe emitted frame order.
- Timeline probing accepts only each frame's literal `pts`. Missing/`N/A`/non-integral,
  duplicate, or nonmonotonic identities fail closed; estimated timestamps, packet
  timestamps, rounded seconds, and nominal-FPS arithmetic are not substituted.
- `RgbFrame` exposes source path, requested index/time, resolved index/time when known,
  dimensions, and `rgb24` bytes.
- The public contract intentionally returns raw RGB bytes and typed metadata, not NumPy or
  PIL objects. Callers convert at their own boundary.
- Sparse index extraction batches unique requested indices into one FFmpeg pass and remaps
  outputs back to the caller's requested order, including duplicate indices.
- Sparse index extraction may switch to seek-window FFmpeg calls for late or widely separated
  requests, using sorted ffprobe packet PTS values to preserve exact frame-index semantics.
- A positive finite `COSMOS_VIDEO_FFMPEG_TIMEOUT` bounds metadata probes, exact timeline
  probes, packet timestamp lookups, and FFmpeg RGB extraction. Unset, blank, invalid,
  non-positive, or non-finite values mean no timeout. Resolver failures, OS-level launch
  failures (including missing or permission-denied executables), timeouts, and non-zero
  process exits remain typed as `VideoProbeError` or `VideoDecodeError`.
- Default implementation is the `ffmpeg-cli` backend through the shared `cosmos.ffmpeg`
  resolver policy. Optional `polli-cosmos[video-av]` installs PyAV/NumPy for explicit
  `COSMOS_VIDEO_BACKEND=pyav` use, or `COSMOS_VIDEO_BACKEND=auto` for a platform-aware
  choice. Auto mode uses PyAV with FFmpeg CLI fallback on macOS and keeps FFmpeg CLI on
  Linux.
- PyAV preserves the `RgbFrame` contract but may produce tiny RGB-byte differences from
  system FFmpeg because the wheel bundles its own libav stack. Keep backend choice explicit
  in benchmark-sensitive callers until downstream tolerance is approved.
- Optional `polli-cosmos[video-torchcodec]` installs PyTorch/TorchCodec/NumPy for explicit
  `COSMOS_VIDEO_BACKEND=torchcodec` CPU benchmarking. TorchCodec tensors are converted back
  to `RgbFrame.rgb24`; do not expose tensors through this public surface.
- Tensor-native decode APIs are deferred until a backend demonstrates a representative
  WFC advantage that is lost when Cosmos materializes public `RgbFrame.rgb24` bytes.

### Ingest

- `ingest(input_dir, output_dir, *, manifest, options) -> list[Path]`
- `IngestOptions` controls quality mode, resolution, dry-run, clip filtering, decoder preference, filter-thread knobs, determinism profile (`profile`), and source adapter selection (`adapter` field).
- Ingest dry-run writes `cosmos_ingest_dry_run.v1.json` with adapter/options
  metadata, typed output declarations, and per-clip executable argv arrays.
- Adapter contract: `IngestAdapter` Protocol in `cosmos.ingest.adapter` — defines `detect()`, `discover_clips()`, `validate_clip()`, `build_ffmpeg_spec()`, `validate_system()`.
- Built-in adapters: `cosm` (COSM C360), `generic-media` (flat video directory). Auto-detected by default; explicit via `IngestOptions.adapter` or CLI `--adapter`.

### Crop

- `crop(input_videos, jobs, out_dir, *, ffmpeg_opts) -> list[Path]`
- Job types:
  - `CropJob` (square mode)
  - `RectCropJob` (rect mode, includes `view_id`, `annotations`)
- `crop()` requires homogeneous job lists (all square or all rect).
- Crop dry-run writes `cosmos_crop_dry_run.json` and returns planned output
  paths without creating placeholder MP4 files or per-output view sidecars.

### Preview

- `preview(input_videos, jobs, out_dir, *, options) -> PreviewRunResult`
- `preview_curated_views(pairs, out_dir, *, options) -> PreviewRunResult`
- `RenderOptions` controls keyframe selectors, stacked overlay times, render scale, diagnostics, and dry-run behavior.
- Preview outputs are bundle-oriented:
  - run-level `cosmos_crop_preview_run.v1.json`
  - per-clip `preview_plan.v1.json` + image artifacts (`frames/`, `sheets/`, `stacked/`)
- `PreviewRect` retains exactly eight serialized preview-plan v1 fields:
  `x_px`, `y_px`, `w_px`, `h_px`, `x_norm`, `y_norm`, `w_norm`, and `h_norm`.
- `PreviewRect.typus_bbox` is a read-only derived `BBoxXYWHNorm | None`; `None`
  means the known lossy normalized rectangle is not representable by Typus, not
  that geometry is missing.

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
  - dry-run plan `cosmos_optimize_dry_run.json` with per-output `command` argv arrays
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

- `cosmos process ...` (canonical ingest -> optional crop workflow)
- `cosmos ingest ...` (supports `--adapter` for source layout selection)
- `cosmos crop ...`
- `cosmos optimize ...`
- `cosmos provenance ...`
- `cosmos lineage ...`
- retired legacy alias: `cosmos pipeline ...` is no longer available; use
  `cosmos process`.

### Process command

- `cosmos process <input_dir> <output_dir>`
  - flow flags: `--post-process`, `--crop-config`
  - run-control flags: `--dry-run`, `--clip`, `--profile`, `--yes/--no-input`, `--skip-ffmpeg-check`
  - output flags: `--json|--plain`

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

### Determinism profile precedence

- `--profile` CLI flag has highest precedence.
- `COSMOS_PROFILE` environment variable is next.
- Per-command defaults apply when neither CLI nor env is set.

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

- `--yes` to suppress prompts on interactive commands that expose it (for example `ingest run`, `crop run`, `optimize run`).
- `--skip-ffmpeg-check` to suppress bootstrap prompt where supported.
- `--dry-run` must avoid side-effectful encode execution and media-output
  writes, while still reporting declared outputs only after inputs/options
  validate.
- Media-execution dry-runs expose `dry_run_plan` in CLI JSON when they write a
  plan artifact.
- Executable plan commands are argv arrays under the v1 plan `commands` list,
  not shell strings.
- machine-safe mode: use `--json` for structured payloads, keep parseable data on stdout.

## Exit-code policy (target contract for redesign)

- `0`: success
- `2`: invalid usage / argument validation failure
- `3`: input validation failure (missing clips/specs/manifests)
- `4`: ffmpeg preflight/bootstrap resolution failure
- `5`: processing failure (ffmpeg run error after preflight)

Current CLI does not fully standardize this map yet; redesign work should align behavior to this contract.
