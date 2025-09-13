# cosmos CLI

Quick start

```
cosmos --help
cosmos ingest run --help
cosmos crop run --help
cosmos pipeline --help
```

Notes
- Ensure `ffmpeg` is installed and available on PATH.
- On macOS, Homebrew: `brew install ffmpeg`. On Ubuntu: `sudo apt-get install ffmpeg`.
- Generated outputs are written in the specified output directory.

Manifest discovery and validation
- If you do not pass `--manifest`, `cosmos ingest` will search the `input_dir` for a single `*.xml` manifest (same pattern as the original tool). If found, it parses clips and validates segments using `meta.json` files.
- System checks validate FFmpeg presence and basic output directory permissions.
- When a manifest is not found, ingest falls back to discovered `.mp4` files for convenience.

Dry runs
- Add `--dry-run` to `cosmos ingest run` or `cosmos pipeline` to build commands without executing FFmpeg. Outputs are simulated so downstream steps can proceed.
