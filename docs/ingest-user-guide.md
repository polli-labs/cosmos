# Ingest User Guide (Cosmos)

This guide walks non‑technical users through installing prerequisites, verifying your system, and converting COSM camera data into standard MP4 files using the `cosmos` tool.

## Quick start (summary)
1) Install Python 3.10+ and FFmpeg (see below).
2) Install Cosmos:
```
uv venv .venv
. .venv/bin/activate
uv pip install -e ".[dev]"
```
3) Run the interactive ingest:
```
cosmos ingest run
```
4) Follow the on‑screen prompts to select your input folder and output folder.

## Install prerequisites
- Python 3.10+ — Windows/macOS/Linux.
- FFmpeg — required by the tool.

### Windows (FFmpeg)
- Download the “release essentials” ZIP from https://www.gyan.dev/ffmpeg/builds/.
- Extract to `C:\ffmpeg`.
- Add `C:\ffmpeg\ffmpeg-…\bin` to your PATH (System Properties → Environment Variables).
- Verify in Command Prompt: `ffmpeg -version`.

### macOS
- Install Homebrew (https://brew.sh) if needed.
- `brew install ffmpeg`
- Verify: `ffmpeg -version`.

### Linux (Ubuntu/Debian)
- `sudo apt update && sudo apt install ffmpeg`
- Verify: `ffmpeg -version`.

## Verify your input
- Ensure your folder matches the expected camera structure (see input-structure.md).
- Place your `*.xml` manifest in the top of the input folder.

## Run ingest (interactive)
```
cosmos ingest run
```
- Select your input folder and output folder.
- Cosmos will validate your system and create an output MP4 for each valid “clip”.

## Run ingest (non‑interactive examples)
- Default quality (balanced), 4K output:
```
cosmos ingest run --input-dir /path/to/input --output-dir ./out --yes
```
- Process specific clips only:
```
cosmos ingest run --input-dir /path/to/input --output-dir ./out --clip CLIP1 --clip CLIP2 --yes
```
- Dry‑run (plan only; writes a JSON plan in output folder):
```
cosmos ingest run --input-dir /path/to/input --output-dir ./out --dry-run --yes
```

## Tuning performance and memory
- Scale filter (speed vs quality): `--scale-filter bicubic|spline36|lanczos`
- Limit filter threads: `--filter-threads 2 --fc-threads 2`
- Short preview: `--window 10` (first 10 seconds only)
- Best‑effort hardware decode: `--decode hw` (falls back automatically if unsupported)

Tip: Large upscales (e.g., 9.28k×6.3k) with the `lanczos` filter are CPU‑heavy and memory‑intensive. For previews, use `balanced` mode, a 4K target, and `--scale-filter bicubic`.

## Output and logs
- Each processed clip creates:
  - `{clip}.mp4` — the output video.
  - `{clip}.mp4.cmd.txt` — the exact ffmpeg command used.
  - `{clip}.mp4.log.txt` — ffmpeg stdout/stderr.
- Dry‑run writes `cosmos_dry_run.json` with encoder preferences, filter graph, and clip plan.

## Troubleshooting
- “ffmpeg not found”: recheck your FFmpeg install and PATH.
- “No manifest found”: pass `--manifest /path/to/file.xml`.
- “Missing segments”: confirm each `…/SS` folder has `meta.json` and `.ts` files.
- Windows long paths: enable long path support or shorten directory names.

