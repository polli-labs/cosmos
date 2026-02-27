# Ingest User Guide

This guide walks through converting COSM camera inputs into MP4 clips with `cosmos ingest run`.

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

## Validate your input structure

Before running ingest, confirm your camera folders match the expected structure in
[Input Structure](input-structure.md).

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
- manifest not found: pass `--manifest /path/to/file.xml`
- missing segments: verify `meta.json` and `.ts` files are present in expected folders
