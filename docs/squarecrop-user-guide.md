# Squarecrop User Guide

This guide helps non‑technical users crop square videos from existing MP4s using the `squarecrop` tool.

## Quick start
1) Install prerequisites (Python + FFmpeg) and Cosmos (see ingest-user-guide.md).
2) Run the interactive crop tool:
```
squarecrop run
```
3) Enter MP4 paths and choose an output folder when prompted.

## Jobs file (recommended)
Squarecrop supports a simple JSON “jobs file” that describes targets and offsets (percent of width/height), and optional trims.

Example `job_settings.json`:
```json
{
  "job_name": "CLIP2_center_offsets",
  "targets": [640, 1080],
  "offset_x": 0.05,
  "offset_y": 0.00,
  "trim_unit": "time",
  "trim_start": "0",
  "trim_end": "10"
}
```

Run with a jobs file:
```
squarecrop run --jobs-file /path/to/job_settings.json --input /path/to/clip.mp4 --out-dir ./crops --yes
```

Notes
- `targets` are square sizes in pixels.
- `offset_x`, `offset_y` shift the crop window from center (positive = right/down).
- `trim_start`, `trim_end` in seconds when `trim_unit` is `time`.
- Multiple `targets` will produce multiple outputs.

## Dry‑run
- Use `--dry-run` to build ffmpeg commands without running them.
- The crop pipeline logs the command and can be integrated into automation.

## Troubleshooting
- Ensure input MP4s are readable (not DRM protected).
- If speed is slow, try smaller targets or shorter trims.

