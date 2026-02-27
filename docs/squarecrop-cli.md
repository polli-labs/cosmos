# squarecrop CLI Reference

`squarecrop` is the standalone crop CLI. It mirrors the crop functionality exposed by
`cosmos crop run`, but provides a direct entrypoint for crop-only workflows.

## Quickstart

```bash
squarecrop --help
squarecrop --input video1.mp4 --out-dir ./out --yes
squarecrop --input video1.mp4 --out-dir ./out --dry-run --yes
squarecrop --input video1.mp4 --out-dir ./out --jobs-file job_settings.json --yes
```

## Interactive mode

Run without required flags to launch guided prompts:

```bash
squarecrop
```

## Non-interactive (agent-friendly) mode

```bash
squarecrop \
  --input clip.mp4 \
  --out-dir _work/out \
  --size 1080 \
  --offset-x 0.2 \
  --offset-y -0.1 \
  --yes
```

Notes:

- Add `--jobs-file` to expand multiple jobs and target sizes.
- `--dry-run` builds commands without encoding.
- Offsets are margin-relative in `[-1, 1]` and should not be mixed with centers.

## Encoder behavior

- Uses platform-preferred hardware encoders when available.
- Falls back to `libx264` when hardware paths are unavailable.
- On macOS with very large inputs, `--prefer-hevc-hw` can avoid H.264 VideoToolbox limits.

For platform caveats and fallback details, see [Encoder Behavior](encoder-behavior.md).

## Jobs file example

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
