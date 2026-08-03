# Crop User Guide

This guide covers crop generation from existing MP4s using `cosmos crop run`.

## Quick start

```bash
cosmos crop run --input /path/to/clip.mp4 --out-dir ./crops --yes
```

Interactive mode is also available:

```bash
cosmos crop run
```

## Jobs file workflow

Use a JSON jobs file for repeatable crop specs or multiple target sizes.

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
cosmos crop run --jobs-file /path/to/job_settings.json --input /path/to/clip.mp4 --out-dir ./crops --yes
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
cosmos crop run --input clip.mp4 --out-dir ./crops --dry-run --yes
```

`--dry-run` validates inputs/jobs and declares crop output paths without encoding.
It writes `cosmos_crop_dry_run.json`, exposes that path as `dry_run_plan` in
`--json` output, and does not create placeholder MP4 files; see
[Agent-Native Dry-Run Contract](dry-run-contract.md).

Real runs write `cosmos_crop_run.v1.json` and per-output
`*.mp4.cosmos_view.v1.json` sidecars. Required artifact sidecar write failures
fail the run.

## Encoder notes

- Cosmos prefers platform hardware encoders and falls back to `libx264` when needed.
- On macOS with large inputs, `--prefer-hevc-hw` can avoid common H.264 VideoToolbox limits.
- See [Encoder Behavior](encoder-behavior.md) for platform details.
