# squarecrop CLI

Standalone square crop tool (also available as `cosmos crop`).

Examples

```
squarecrop --input video1.mp4 --input video2.mp4 --yes --out-dir ./out
squarecrop --input video1.mp4 --out-dir ./out --dry-run
squarecrop --input video1.mp4 --out-dir ./out --jobs-file /path/to/job_settings.json
```

Interactive mode
- Omit flags to be prompted for inputs and output directory.

Notes
- Uses your system encoder when available (VideoToolbox/NVENC/QSV), falling back to `libx264`.
- macOS: H.264 VideoToolbox typically rejects >4K inputs; pass `--prefer-hevc-hw` to try `hevc_videotoolbox` first on large inputs. Provenance records the attempted/used encoder either way.
- Platform behavior matrix: see `docs/encoder-behavior.md`.
- `--dry-run` builds FFmpeg commands without execution (useful for CI or previews).
- `--jobs-file` accepts a SquareCrop-style JSON (offset_x/offset_y, targets, optional trims) and expands to multiple crop jobs.
