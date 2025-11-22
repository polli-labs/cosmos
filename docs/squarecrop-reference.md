# Squarecrop CLI Reference

Top-level command
- `squarecrop run` — run interactive or non‑interactive square cropping.

Options
- `--input PATH` — one or more MP4 files (repeatable).
- `--out-dir PATH` — output directory.
- `--jobs-file PATH` — JSON jobs file (targets/offsets/trims).
- `--dry-run` — do not execute ffmpeg; show planned commands.
- `--yes` — non‑interactive.

Examples
- Simple interactive use:
```
squarecrop run
```
- Non‑interactive with jobs file:
```
squarecrop run --jobs-file /path/jobs.json --input clip.mp4 --out-dir ./out --yes
```
- Multiple inputs:
```
squarecrop run --jobs-file /path/jobs.json --input a.mp4 --input b.mp4 --out-dir ./out --yes
```

Jobs file fields
- `targets`: list of square sizes (e.g., `[640,1080]`).
- `offset_x`, `offset_y`: relative-to-margin offsets in range [-1.0, 1.0]. 0 means centered; positive is right/down; negative is left/up. This mirrors legacy CENTER_TARGET behavior. Offsets take precedence over centers.
- `center_x`, `center_y` (optional): absolute center in [0.0, 1.0] of full width/height (used when offsets are not set). Do not combine offsets with centers.
- `trim_unit`: currently `time`.
- `trim_start`, `trim_end`: strings or numbers representing seconds, applied when `trim_unit` is `time`.

Notes
- Multiple jobs/targets are all applied per input; outputs are named with job and size markers for traceability.
- Provenance: each output gets `.cosmos_view.v1.json` with crop offsets/centers, trim info, video width/height/duration/fps, and stable `view_id`.
