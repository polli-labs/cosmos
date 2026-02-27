# Squarecrop User Guide

This guide covers square crop generation from existing MP4s using `squarecrop`.

## Quick start

```bash
squarecrop --input /path/to/clip.mp4 --out-dir ./crops --yes
```

Interactive mode is also available:

```bash
squarecrop
```

## Jobs file workflow (recommended)

Use a JSON jobs file when you need multiple target sizes or repeatable crop specs.

Example `job_settings.json`:

```json
{
  "job_name": "CLIP2_center_offsets",
  "targets": [640, 1080],
  "offset_x": 0.05,
  "offset_y": 0.0,
  "trim_unit": "time",
  "trim_start": "0",
  "trim_end": "10"
}
```

Run with jobs file:

```bash
squarecrop --jobs-file /path/to/job_settings.json --input /path/to/clip.mp4 --out-dir ./crops --yes
```

## Crop semantics

- Preferred: `offset_x`, `offset_y` in `[-1, 1]`, relative to available crop margin
- Alternative: `center_x`, `center_y` in `[0, 1]`
- Do not mix offsets and centers in the same job

Additional fields:

- `targets`: one or more square output sizes
- `trim_start`, `trim_end` when `trim_unit` is `time`

## Dry-run and automation

```bash
squarecrop --input clip.mp4 --out-dir ./crops --dry-run --yes
```

`--dry-run` generates plans/commands without encoding.

## Encoder notes

- Cosmos prefers platform hardware encoders and falls back to `libx264` when needed.
- On macOS with large inputs, `--prefer-hevc-hw` can avoid common H.264 VideoToolbox limits.
- See [Encoder Behavior](encoder-behavior.md) for platform details.
