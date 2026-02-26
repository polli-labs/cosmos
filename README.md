# Cosmos

Unified ingest + post‑processing toolkit

- `cosmos`: COSM camera MP4 generation (ingest) and orchestration
- `squarecrop`: general MP4 post‑processing (square crop)

Two CLIs, one SDK. TUI‑first UX with a stable programmatic API.

## Install

- Production: `pip install polli-cosmos`
- Dev (uv): 
  ```
  uv venv .venv
  . .venv/bin/activate
  uv pip install -e ".[dev]"
  ```

## CLI quickstart

```
cosmos --help
cosmos process --help
cosmos ingest run --help
cosmos crop run --help
cosmos optimize run --help
cosmos crop preview --help
squarecrop --help
```

See docs/cosmos-cli.md and docs/squarecrop-cli.md for usage.

## Local runs (uv + make)

1) Create venv and install dev deps
```
make uv-sync
```

2) Run ingest (example)
```
make run.ingest IN=/path/to/raw OUT=./out YES=1 WINDOW=10
```

3) Run squarecrop with a jobs JSON
```
make run.crop INPUT=/path/to/clip.mp4 OUT=_work/out JOBS=_work/job.json YES=1
```

4) Render crop previews (contact sheets + stacked overlays)
```
cosmos crop preview --input /path/to/clip.mp4 --jobs-file _work/job.json --out _work/preview --frame start --frame mid --stack-time 0 --yes
```

5) Inspect provenance
```
make run.provenance DIR=_work/out
```

6) Optimize outputs for web delivery (faststart remux by default)
```
cosmos optimize run --input /path/to/clip.mp4 --out-dir _work/web --yes
```

Jobs JSON fields for squarecrop:
- `targets`: [1536] or multiple sizes
- Offsets (recommended): `offset_x`, `offset_y` in [-1,1], relative to available margin (0=center; +right/down; −left/up)
- Alternative: `center_x`, `center_y` absolute [0..1] of full frame
- Optional trims: `trim_unit: "time"`, `trim_start`, `trim_end`
- All jobs/targets run for each input; outputs include job/size markers in filenames for traceability.
- Provenance files now include width/height/duration/fps and stable clip/view ids usable by downstream tools.

## IDs & provenance
- Clip IDs: `clip-<stem>-<sha8>`; View IDs: `view-<stem>-<sha8>` (content-hash based, deterministic).
- View provenance records offsets/centers, trim windows (seconds), target size, encoder used, and source clip id/sha.
- Optimize provenance records transform mode/flags plus source/output hashes for rollback-safe workflows.
- Video metadata (width_px/height_px/fps/duration_sec) is recorded in both clip and view artifacts; width/height are aliases for backward compatibility.

## SDK quickstart

```python
from pathlib import Path
from cosmos.sdk import ingest, IngestOptions

inputs = Path("/path/to/raw")
outputs = Path("./out")
opts = IngestOptions(quality_mode="balanced", width=3840, height=2160)
produced = ingest(inputs, outputs, manifest=None, options=opts)
```

## Slim E2E (local, optional)

- Set `COSMOS_ENABLE_LOCAL_TESTS=1`
- Run all local tests: `pytest -q tests/e2e_local`
- Slim ingest reproduction (default): `make e2e-repro-slim`
  - 4K balanced, 10s window, bicubic scaler; writes `{clip}.cmd.txt` and `{clip}.log.txt` alongside outputs.
- 8K windowed reproduction (heavy, local-only): `make e2e-repro-8k` (uses `COSMOS_RUN_8K_REPRO=1`)
  - defaults: `CLIP1`, 2s window, 7680x4320 output
  - optional knobs: `COSMOS_8K_CLIPS`, `COSMOS_8K_WINDOW_SECONDS`, `COSMOS_8K_QUALITY_MODE`, `COSMOS_8K_SCALE_FILTER`
  - CI boundary: skipped when `CI=1` unless `COSMOS_RUN_8K_IN_CI=1`
- Full 9.5k reproduction (very heavy): `make e2e-repro-full` (uses `COSMOS_FULL_REPRO=1`).
- Fixtures live under `/Users/.../ladybird` or `dev/fixtures/cache` (see dev/fixtures/README.md). CI skips these.

## Dev workflow

- Format + lint: `make fmt && make lint`
- Type‑check: `make typecheck`
- Tests: `make test`

## Encoder policy (cross‑platform)

- macOS: `h264_videotoolbox` > `libx264` (use `--prefer-hevc-hw` on large inputs to try `hevc_videotoolbox` first)
- Linux: `h264_nvenc` > `h264_qsv` > `h264_vaapi` > `libx264`
- Windows: `h264_nvenc` > `h264_qsv` > `h264_amf` > `libx264`

Presets are centralized; filter graphs are CPU‑bound (crop/hstack/vstack/scale). Use `--scale-filter` and thread flags to tune throughput and memory.
Auto-selected hardware encoders are runtime-probed on real inputs; Cosmos falls back to `libx264` if the host advertises a hardware encoder that is not actually usable.
Detailed platform behavior and known limits are tracked in `docs/encoder-behavior.md`.
