# Crop Run CLI Reference

Top-level command
- `cosmos crop run` — crop one or more MP4 inputs.

Options
- `--input PATH` — one or more MP4 files (repeatable).
- `--out-dir PATH` — output directory.
- `--jobs-file PATH` — JSON jobs file (targets/offsets/trims).
- `--dry-run` — validate inputs/jobs and declare crop output paths without
  executing ffmpeg or creating placeholder MP4 files. JSON stdout exposes
  `run_artifact`, `dry_run_plan`, and typed `output_declarations`; the plan
  artifact is `cosmos_crop_dry_run.json`.
- `--yes` — non‑interactive.
- `--prefer-hevc-hw` — macOS only: prefer `hevc_videotoolbox` when available.

Examples
- Simple interactive use:
```bash
cosmos crop run
```
- Non-interactive with jobs file:
```bash
cosmos crop run --jobs-file /path/jobs.json --input clip.mp4 --out-dir ./out --yes
```
- Multiple inputs:
```bash
cosmos crop run --jobs-file /path/jobs.json --input a.mp4 --input b.mp4 --out-dir ./out --yes
```

Jobs file fields
- `targets`: list of square sizes (e.g., `[640,1080]`).
- `offset_x`, `offset_y`: relative-to-margin offsets in range [-1.0, 1.0]. 0 means centered; positive is right/down; negative is left/up. This mirrors legacy CENTER_TARGET behavior. Offsets take precedence over centers.
- `center_x`, `center_y` (optional): absolute center in [0.0, 1.0] of full width/height (used when offsets are not set). Do not combine offsets with centers.
- `trim_unit`: currently `time`.
- `trim_start`, `trim_end`: strings or numbers representing seconds, applied when `trim_unit` is `time`.

Notes
- Multiple jobs/targets are all applied per input; outputs are named with job and size markers for traceability.
- Provenance: real runs write `cosmos_crop_run.v1.json` and one
  `.cosmos_view.v1.json` per output with crop geometry, trim info, video
  metadata, source/output sha256 values, and stable `view_id`.
- Dry-runs write `cosmos_crop_run.v1.json` and `cosmos_crop_dry_run.json`; they
  do not write media outputs or per-output view sidecars.
- Platform-specific encoder behavior and limitations are documented in `docs/encoder-behavior.md`.
- The dry-run plan contract is documented in
  [Agent-Native Dry-Run Contract](dry-run-contract.md).
