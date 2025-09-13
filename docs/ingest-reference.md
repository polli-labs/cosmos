# Ingest CLI Reference

Top-level command
- `cosmos ingest run` — run interactive or non‑interactive ingest.

Common options
- `--input-dir PATH` — input directory (root containing `0H/0M/…` and a manifest).
- `--output-dir PATH` — output directory.
- `--yes` — non‑interactive (don’t prompt).
- `--manifest PATH` — manifest XML if not in `--input-dir`.
- `--clip NAME` — process only these clip names (repeatable).
- `--dry-run` — do not execute ffmpeg; write a plan JSON.

Performance tuning
- `--scale-filter` — one of `lanczos|spline36|bicubic|bilinear`.
- `--filter-threads N` — set `-filter_threads`.
- `--fc-threads N` — set `-filter_complex_threads`.
- `--decode {auto|hw|sw}` — best‑effort decode acceleration.
- `--window SECONDS` — process only the first N seconds.

Examples
- Balanced 4K default:
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --yes
```
- Only CLIP1 and CLIP2:
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --clip CLIP1 --clip CLIP2 --yes
```
- Faster preview (bicubic, limited filter threads, 10s):
```
cosmos ingest run --input-dir /data/cosm --output-dir ./out --scale-filter bicubic --filter-threads 2 --fc-threads 2 --window 10 --yes
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

