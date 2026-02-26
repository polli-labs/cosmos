# cosmos CLI

Quick start

```
cosmos --help
cosmos process --help
cosmos ingest run --help
cosmos crop run --help
cosmos optimize run --help
cosmos crop preview --help
cosmos crop curated-views-preview --help
```

Notes
- Ensure `ffmpeg` is installed and available on PATH.
- On macOS, Homebrew: `brew install ffmpeg`. On Ubuntu: `sudo apt-get install ffmpeg`.
- Generated outputs are written in the specified output directory.

Manifest discovery and validation
- If you do not pass `--manifest`, `cosmos ingest` will search the `input_dir` for a single `*.xml` manifest (same pattern as the original tool). If found, it parses clips and validates segments using `meta.json` files.
- System checks validate FFmpeg presence and basic output directory permissions.
- When a manifest is not found, ingest falls back to discovered `.mp4` files for convenience.

Dry runs
- Add `--dry-run` to `cosmos ingest run` or `cosmos pipeline` to build commands without executing FFmpeg. Outputs are simulated so downstream steps can proceed.

Output modes
- Commands that produce result lists now support:
  - `--json`: structured machine output to `stdout`
  - `--plain`: stable line-based output to `stdout`
- Diagnostics, warnings, and deprecation notices are written to `stderr`.

Optimize command
- `cosmos optimize run` is the canonical web-readiness command for existing MP4 outputs.
- Modes:
  - `auto` (default): remux unless transform flags imply transcode
  - `remux`: stream copy + optional faststart atom relocation
  - `transcode`: re-encode with optional `--target-height`, `--fps`, `--crf`
- Key flags:
  - `--input` (repeatable), `--out-dir`, `--mode`
  - `--target-height`, `--fps`, `--crf`, `--encoder` (transcode path)
  - `--faststart/--no-faststart`, `--suffix`, `--force`
  - `--yes/--no-input`, `--dry-run`, `--skip-ffmpeg-check`, `--json|--plain`
- Artifacts:
  - run-level `cosmos_optimize_run.v1.json`
  - per-output `*.mp4.cosmos_optimized.v1.json` (non-dry-run)

Process command
- `cosmos process` is the canonical ingest -> optional crop workflow command.
- `cosmos pipeline` remains as a deprecated compatibility alias.

Crop preview commands
- `cosmos crop preview` renders non-interactive contact-sheet + stacked overlay previews from jobs (or single flag-defined crop).
- `cosmos crop curated-views-preview` does the same for curated-view specs grouped by source clip.
- Shared preview flags:
  - `--frame` for keyframe selectors (`start`, `mid`, `end`, `start+2.0`, `12.5`)
  - `--stack-time` for absolute stacked-overlay times
  - `--render-max-width`, `--grid-step-px`, `--show-rulers/--no-rulers`, `--show-crosshair/--no-crosshair`, `--alpha`
  - `--dry-run` to emit plans/paths without rendering images

Preview outputs
- Run summary: `cosmos_crop_preview_run.v1.json`
- Per-clip bundle: `preview_<clip>_<hash>/`
  - `preview_plan.v1.json`
  - `frames/*.png`
  - `sheets/sheet_frame_<selector>.png`
  - `stacked/stacked_t_<time>.png`
