# Ingest User Guide

This guide walks through ingesting video sources into normalized MP4 clips with `cosmos ingest run`. Cosmos supports multiple source layouts through its adapter system and auto-detects the correct one.

## Prerequisites

- Python 3.10+
- ffmpeg available on PATH

### Install ffmpeg

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt update && sudo apt install ffmpeg`
- Windows: install from https://www.gyan.dev/ffmpeg/builds/ and add `.../bin` to PATH

Verify:

```bash
ffmpeg -version
```

## Install Cosmos

```bash
uv venv .venv
. .venv/bin/activate
uv pip install -e ".[dev]"
```

## Source adapters

Cosmos auto-detects the source layout when you point `--input-dir` at a directory:

| Adapter | Auto-detected when | What it does |
|---|---|---|
| **cosm** | `*.xml` manifest in root | Parses COSM C360 manifest, validates TS segments, applies quad-tile stitch filter graph |
| **generic-media** | Video files present (`.mp4`, `.mov`, `.mkv`, etc.) | Treats each video file as a clip, re-encodes with scaling |

To override auto-detection, pass `--adapter NAME`:

```bash
cosmos ingest run --input-dir /data/videos --output-dir ./out --adapter generic-media --yes
```

## Validate your input structure

For COSM sources, confirm your camera folders match the expected structure in
[Input Structure](input-structure.md).

For generic media, any directory with video files works.

## Run ingest

### Interactive

```bash
cosmos ingest run
```

### Non-interactive

```bash
cosmos ingest run --input-dir /path/to/input --output-dir ./out --yes
```

Useful variants:

```bash
# Process only selected clips
cosmos ingest run --input-dir /path/to/input --output-dir ./out --clip CLIP1 --clip CLIP2 --yes

# Dry-run only (plan, no ffmpeg execution)
cosmos ingest run --input-dir /path/to/input --output-dir ./out --dry-run --yes

# Ingest a directory of standalone MP4s
cosmos ingest run --input-dir /data/field-videos --output-dir ./out --yes
```

## Performance and memory tuning

- Scale filter: `--scale-filter bicubic|spline36|lanczos`
- Filter threads: `--filter-threads 2 --fc-threads 2`
- Short preview window: `--window 10`
- Best-effort hardware decode: `--decode hw`

For large sources, start with balanced quality, a short window, and `bicubic`.

## Outputs and logs

Each processed clip produces:

- `{clip}.mp4`
- `{clip}.mp4.cmd.txt` (exact ffmpeg command)
- `{clip}.mp4.log.txt` (ffmpeg output)

Dry-run writes `cosmos_dry_run.json` with planned commands and clip plan.

## Troubleshooting

- ffmpeg not found: verify install and PATH
- "No adapter could handle": your directory has no XML manifest and no video files — check contents
- manifest not found (COSM): ensure `*.xml` is in the input root
- missing segments (COSM): verify `meta.json` and `.ts` files are present in expected folders
