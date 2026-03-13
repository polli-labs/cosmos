# Provenance (v1)

Cosmos emits machine-readable JSON artifacts that document how media was produced.
These artifacts support reproducibility, auditability, and stable downstream joins.

## Artifact categories

### Run-level artifacts

- `cosmos_ingest_run.v1.json`: ingest environment, options, encoder preferences
- `cosmos_crop_run.v1.json`: crop jobs and environment
- `cosmos_optimize_run.v1.json`: optimize mode/options, hashes, environment
- `cosmos_crop_preview_run.v1.json`: preview selectors, render options, per-clip plans

### Artifact-level sidecars

- `*.mp4.cosmos_clip.v1.json`: ingest output metadata and hash
- `*.mp4.cosmos_view.v1.json`: crop output metadata, source linkage, hash
- `*.mp4.cosmos_optimized.v1.json`: optimize output metadata, source linkage, hash
- `preview_<clip>_<hash>/preview_plan.v1.json`: per-clip preview contract and output map

## Canonical join keys

- `view.source.sha256 == clip.output.sha256`
- `optimized.source.sha256` may match either ingest clip output or crop view output
- `clip.ingest_run_id` joins to ingest run-level files
- `view.crop_run_id` joins to crop run-level files

## Schema reference

- [ingest_run.v1.json](schemas/ingest_run.v1.json)
- [clip.v1.json](schemas/clip.v1.json)
- [crop_run.v1.json](schemas/crop_run.v1.json)
- [view.v1.json](schemas/view.v1.json)
- [optimize_run.v1.json](schemas/optimize_run.v1.json)
- [optimized.v1.json](schemas/optimized.v1.json)
- [crop_preview_run.v1.json](schemas/crop_preview_run.v1.json)
- [crop_preview_plan.v1.json](schemas/crop_preview_plan.v1.json)

## Example clip artifact

```json
{
  "$schema": "https://docs.polli.ai/cosmos/schemas/clip.v1.json",
  "schema_version": "1.0.0",
  "clip_id": "clip_...",
  "ingest_run_id": "ing_...",
  "name": "CLIP1",
  "output": {"path": "clips/CLIP1.mp4", "sha256": "...", "bytes": 12345678},
  "video": {
    "width": 4096,
    "height": 2160,
    "fps": 29.97,
    "pix_fmt": "yuv420p",
    "color_space": "bt709"
  },
  "encode": {"impl": "h264_nvenc", "crf": 18, "filtergraph": "..."},
  "env": {
    "ffmpeg": {"version": "ffmpeg 6.1.1 ..."},
    "system": {"os": "macOS 14.6 ..."}
  }
}
```

## Lineage graph

Cosmos can build a directed acyclic graph (DAG) from provenance sidecars to answer
upstream/downstream questions across pipeline stages.

```bash
# Build and inspect the lineage index
cosmos lineage build /path/to/outputs --json

# What was this optimized artifact made from?
cosmos lineage upstream <sha256-or-id> --in /path/to/outputs --json

# What derivatives exist for this clip?
cosmos lineage downstream <sha256-or-id> --in /path/to/outputs --json

# Full chain (ancestors + self + descendants)
cosmos lineage chain <sha256-or-id> --in /path/to/outputs --json

# Nested source tree
cosmos lineage tree <sha256-or-id> --in /path/to/outputs --json
```

The lineage index is built deterministically from sidecar files and uses the same
sha256 join keys documented above. See the [CLI reference](cosmos-cli.md#lineage-graph-queries)
for full command documentation.

## Operational guidance

- Keep sidecar JSON files with the MP4s when copying outputs.
- Dry-runs emit run-level plans only; artifact sidecars require real outputs.
- Preview bundles are designed for GUI seed workflows:
  - `preview_plan.v1.json` is the machine contract
  - image artifacts (`frames`, `sheets`, `stacked`) are review outputs
