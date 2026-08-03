# Ingest CLI Reference

Top-level command
- `cosmos ingest run` — normalize source clips into MP4 outputs.

Source adapter selection
- `--adapter NAME` — choose source adapter explicitly (`cosm` or `generic-media`). When omitted, auto‑detected from directory contents.

Common options
- `--input-dir PATH` — input directory.
- `--output-dir PATH` — output directory.
- `--yes` — non‑interactive (don't prompt).
- `--clip NAME` — process only these clip names (repeatable).
- `--dry-run` — validate and declare outputs without creating media outputs; write
  `cosmos_ingest_dry_run.v1.json` with adapter/options metadata, typed output
  declarations, and per-clip argv arrays.

Performance tuning
- `--scale-filter` — one of `lanczos|spline36|bicubic|bilinear`.
- `--filter-threads N` — set `-filter_threads`.
- `--fc-threads N` — set `-filter_complex_threads`.
- `--decode {auto|hw|sw}` — best‑effort decode acceleration.
- `--window SECONDS` — process only the first N seconds.

## Adapters

### cosm (default for COSM cameras)
Auto-detected when the input directory contains a `*.xml` manifest. Handles the COSM C360 quad-tile TS-segment layout: manifest parsing, segment validation, and the stitch filter graph.

### generic-media
Auto-detected when the input directory contains video files (`.mp4`, `.mov`, `.mkv`, `.avi`, `.ts`, `.mts`, `.webm`) but no COSM manifest. Each video file is one clip and is re-encoded with optional scaling.

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
- run-level and per-clip provenance sidecars for real outputs.
- `cosmos_ingest_dry_run.v1.json` — v1 dry-run plan for all clips when
  `--dry-run` is used.
