# Ingest CLI Reference

Top-level command
- `cosmos ingest run` — run interactive or non‑interactive ingest.

Source adapter selection
- `--adapter NAME` — choose source adapter explicitly (`cosm` or `generic-media`). When omitted, auto‑detected from directory contents.

Common options
- `--input-dir PATH` — input directory.
- `--output-dir PATH` — output directory.
- `--yes` — non‑interactive (don't prompt).
- `--clip NAME` — process only these clip names (repeatable).
- `--dry-run` — do not execute ffmpeg; write a plan JSON.

Performance tuning
- `--scale-filter` — one of `lanczos|spline36|bicubic|bilinear`.
- `--filter-threads N` — set `-filter_threads`.
- `--fc-threads N` — set `-filter_complex_threads`.
- `--decode {auto|hw|sw}` — best‑effort decode acceleration.
- `--window SECONDS` — process only the first N seconds.

## Adapters

### cosm (default for COSM cameras)
Auto-detected when the input directory contains a `*.xml` manifest. Handles the COSM C360 quad-tile TS-segment layout: manifest parsing, segment validation, and a filter graph that crops, hstacks, and vstacks four tile streams.

### generic-media
Auto-detected when the input directory contains video files (`.mp4`, `.mov`, `.mkv`, `.avi`, `.ts`, `.mts`, `.webm`) but no COSM manifest. Each video file is treated as a single clip and re-encoded with optional scaling — no tile-stitching filter graph.

Examples
- Balanced 4K default (COSM auto-detected):
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --yes
```
- Only CLIP1 and CLIP2:
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --clip CLIP1 --clip CLIP2 --yes
```
- Generic media (auto-detected):
```
cosmos ingest run --input-dir /data/videos --output-dir ./out --yes
```
- Force generic adapter on a COSM directory:
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --adapter generic-media --yes
```
- Dry‑run plan only:
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --dry-run --yes
```

Outputs
- `{clip}.mp4` — output video.
- `{clip}.mp4.cmd.txt` — exact ffmpeg command.
- `{clip}.mp4.log.txt` — ffmpeg logs.
- `cosmos_dry_run.json` — plan for all clips when `--dry-run` is used.
