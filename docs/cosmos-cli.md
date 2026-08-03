# cosmos CLI Reference

`cosmos` is the CLI for ingest, crop, optimize, preview, provenance lookup,
and lineage queries.

## Command map

- `cosmos process`: run ingest plus optional crop from one root command
- `cosmos ingest run`: normalize source layouts into MP4 clips
- `cosmos crop run`: crop existing MP4s in square or rect mode
- `cosmos crop preview`: write contact-sheet and stacked-overlay QA previews
- `cosmos crop curated-views`: execute curated-view specs
- `cosmos crop curated-views-preview`: preview curated-view specs
- `cosmos optimize run`: remux or transcode MP4s for web delivery
- `cosmos provenance ...`: hash and lookup produced artifacts
- `cosmos lineage ...`: query provenance graph ancestry and descendants

Retired alias:

- `cosmos pipeline` has been retired. Use `cosmos process`.

## Global behavior contracts

- Ensure `ffmpeg` is available (`COSMOS_FFMPEG` override is supported).
- Automation-safe output modes:
  - `--json`: structured payload to stdout
  - `--plain`: line-oriented payload to stdout
- Diagnostics and warnings are emitted to stderr.
- `--yes` suppresses interactive prompts for non-TTY automation.
- `--dry-run` avoids applying the planned media transform or creating media
  outputs, while still allowing bounded local preflight/probing.
  Media-execution commands expose typed output declarations and dry-run plan
  artifacts; use
  [Agent-Native Dry-Run Contract](dry-run-contract.md).

## Root workflow

`cosmos process` is the canonical visible root workflow for ingesting a source
directory and optionally running crop jobs afterward.

```bash
cosmos process --help
cosmos process /path/raw ./out --plain
cosmos process /path/raw ./out --post-process --crop-config jobs.json --plain
cosmos process /path/raw ./out --dry-run --json
```

`cosmos process` supports `--yes/--no-input`, `--skip-ffmpeg-check`,
`--json|--plain`, and dry-run planning. Use the child commands directly when
you need command-specific flags beyond the root workflow.

## Ingest

```bash
cosmos ingest run --help
cosmos ingest run --input-dir /path/in --output-dir /path/out --yes
cosmos ingest run --input-dir /path/in --output-dir /path/out --clip CLIP1 --clip CLIP2 --yes
cosmos ingest run --input-dir /path/in --output-dir /path/out --dry-run --yes
```

Manifest behavior:

- If `--manifest` is omitted, Cosmos searches `input_dir` for a single `*.xml` manifest.
- If no manifest is found, ingest can use the `generic-media` adapter for
  discovered video files.

Artifacts:

- `{clip}.mp4`
- `{clip}.mp4.cmd.txt`
- `{clip}.mp4.log.txt`
- `cosmos_ingest_dry_run.v1.json` when `--dry-run` is used. JSON stdout exposes
  it as `dry_run_plan`.

## Crop

```bash
cosmos crop run --help
cosmos crop run --input clip.mp4 --out-dir ./out --size 1080 --offset-x 0.1 --offset-y 0 --yes
cosmos crop run --input clip.mp4 --out-dir ./out --jobs-file jobs.json --yes
cosmos crop run --input clip.mp4 --out-dir ./out --crop-mode rect --x0 0.1 --y0 0.1 --width 0.5 --height 0.5 --yes
```

Preview commands:

```bash
cosmos crop preview --input clip.mp4 --jobs-file jobs.json --out ./preview --frame start --frame mid --stack-time 0 --yes
cosmos crop curated-views-preview --spec curated_views.json --source-root /data --out ./preview --frame start --frame end --yes
```

Artifacts:

- Crop run: `cosmos_crop_run.v1.json` plus per-output
  `*.mp4.cosmos_view.v1.json` sidecars on real runs.
- Preview: `cosmos_crop_preview_run.v1.json` plus per-clip
  `preview_plan.v1.json` and image bundles.
- Dry-run crop execution writes `cosmos_crop_dry_run.json`, exposes it as
  `dry_run_plan`, and declares outputs without creating placeholder MP4 files.

## Optimize

`cosmos optimize run` is the canonical web-readiness path for existing MP4 outputs.

```bash
cosmos optimize run --help
cosmos optimize run --input clip.mp4 --out-dir ./web --yes
cosmos optimize run --input clip.mp4 --out-dir ./web --mode transcode --target-height 1080 --fps 30 --crf 23 --yes
```

Modes:

- `auto` (default): remux unless transform flags imply transcode
- `remux`: stream copy + optional `faststart` atom relocation
- `transcode`: re-encode with optional scale/fps/crf transforms

Key flags:

- Inputs/output: `--input` (repeatable), `--out-dir`
- Mode/transforms: `--mode`, `--target-height`, `--fps`, `--crf`, `--encoder`
- Safety and naming: `--faststart/--no-faststart`, `--suffix`, `--force`
- Determinism: `--profile strict|balanced|throughput` (controls encoder, threads, bitexact)
- Automation: `--yes/--no-input`, `--dry-run`, `--skip-ffmpeg-check`, `--json|--plain`

Optimize artifacts:

- Run-level: `cosmos_optimize_run.v1.json`
- Per-output: `*.mp4.cosmos_optimized.v1.json` (non-dry-run)
- Dry-run plan: `cosmos_optimize_dry_run.json`, exposed as `dry_run_plan` in
  `--json` output and populated with argv-array `command` entries.

Encoder resilience:

- In auto mode, Cosmos performs a runtime viability probe for hardware encoders and
  falls back to `libx264` if the advertised hardware path is not actually usable.
- If `--encoder` is explicitly provided, Cosmos treats that choice as authoritative and
  surfaces ffmpeg failure directly.

## Lineage graph queries

`cosmos lineage` provides graph traversal over provenance sidecar artifacts
across ingest, crop, and optimize stages.

```bash
cosmos lineage build /path/to/output-dir --json
cosmos lineage build /path/to/output-dir --output lineage.json
cosmos lineage upstream <sha256-or-id> --in /path/to/output-dir --json
cosmos lineage downstream <sha256-or-id> --in /path/to/output-dir --json
cosmos lineage chain <sha256-or-id> --in /path/to/output-dir --json
cosmos lineage tree <sha256-or-id> --in /path/to/output-dir --json
```

Commands:

- `build`: Scan directories for provenance sidecars and build a lineage index (optionally write to file).
- `upstream`: Show all transitive ancestors of an artifact.
- `downstream`: Show all transitive derivatives of an artifact.
- `chain`: Show the full lineage chain (upstream + self + downstream).
- `tree`: Show nested upstream source hierarchy.

Identifiers accept full sha256, sha256 prefix, or artifact IDs (e.g., `clip-CLIP1-abc12345`).

## Provenance helpers

```bash
cosmos provenance --help
cosmos provenance map /path/to/output-dir
```

See [Provenance](provenance.md) for join-key guidance and schema links.
