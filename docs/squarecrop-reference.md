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
- `offset_x`, `offset_y`: fractional offsets from center (0.0..1.0 typical).
- `trim_unit`: currently `time`.
- `trim_start`, `trim_end`: strings or numbers representing seconds, applied when `trim_unit` is `time`.

