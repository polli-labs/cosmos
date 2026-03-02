# cosmos CLI Reference

`cosmos` is the primary CLI for ingest, crop, optimize, preview, and provenance helpers.

## Command map

- `cosmos ingest run`: process camera inputs into MP4 clips
- `cosmos crop run`: crop existing MP4s (square and rect modes)
- `cosmos crop preview`: generate contact-sheet and stacked-overlay previews
- `cosmos crop curated-views`: execute curated-view specs
- `cosmos crop curated-views-preview`: preview curated-view specs
- `cosmos optimize run`: remux/transcode MP4s for web delivery
- `cosmos provenance ...`: lookup/hash helpers for produced artifacts

Legacy alias:

- `cosmos process` remains available for compatibility workflows.

## Global behavior contracts

- Ensure `ffmpeg` is available (`COSMOS_FFMPEG` override is supported).
- Automation-safe output modes:
  - `--json`: structured payload to stdout
  - `--plain`: line-oriented payload to stdout
- Diagnostics and warnings are emitted to stderr.
- `--yes` suppresses interactive prompts for non-TTY automation.
- `--dry-run` generates plans/commands without running ffmpeg.

## Ingest quick references

```bash
cosmos ingest run --help
cosmos ingest run --input-dir /path/in --output-dir /path/out --yes
cosmos ingest run --input-dir /path/in --output-dir /path/out --clip CLIP1 --clip CLIP2 --yes
cosmos ingest run --input-dir /path/in --output-dir /path/out --dry-run --yes
```

Manifest behavior:

- If `--manifest` is omitted, Cosmos searches `input_dir` for a single `*.xml` manifest.
- If no manifest is found, ingest can fall back to discovered `.mp4` files for convenience.

## Crop quick references

```bash
cosmos crop run --help
cosmos crop run --input clip.mp4 --out-dir ./out --size 1080 --offset-x 0.1 --offset-y 0 --yes
cosmos crop run --input clip.mp4 --out-dir ./out --jobs-file jobs.json --yes
```

Preview commands:

```bash
cosmos crop preview --input clip.mp4 --jobs-file jobs.json --out ./preview --frame start --frame mid --stack-time 0 --yes
cosmos crop curated-views-preview --spec curated_views.json --source-root /data --out ./preview --frame start --frame end --yes
```

## Optimize quick references

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

Encoder resilience:

- In auto mode, Cosmos performs a runtime viability probe for hardware encoders and
  falls back to `libx264` if the advertised hardware path is not actually usable.
- If `--encoder` is explicitly provided, Cosmos treats that choice as authoritative and
  surfaces ffmpeg failure directly.

## Provenance helpers

```bash
cosmos provenance --help
cosmos provenance map /path/to/output-dir
```

See [Provenance](provenance.md) for join-key guidance and schema links.
