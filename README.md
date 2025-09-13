# Cosmos

Unified ingest + post‑processing toolkit

- `cosmos`: COSM camera MP4 generation (ingest) and orchestration
- `squarecrop`: general MP4 post‑processing (square crop)

Two CLIs, one SDK. TUI‑first UX with a stable programmatic API.

## Install (uv)

```
uv venv .venv
. .venv/bin/activate
uv pip install -e ".[dev]"
```

## CLI quickstart

```
cosmos --help
cosmos ingest run --help
cosmos crop run --help
squarecrop --help
```

See docs/cosmos-cli.md and docs/squarecrop-cli.md for usage.

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
- Full 9.5k reproduction (very heavy): `make e2e-repro-full` (uses `COSMOS_FULL_REPRO=1`).
- Fixtures live under `/Users/.../ladybird` or `dev/fixtures/cache` (see dev/fixtures/README.md). CI skips these.

## Dev workflow

- Format + lint: `make fmt && make lint`
- Type‑check: `make typecheck`
- Tests: `make test`

## Encoder policy (cross‑platform)

- macOS: `h264_videotoolbox` > `libx264`
- Linux: `h264_nvenc` > `h264_qsv` > `h264_vaapi` > `libx264`
- Windows: `h264_nvenc` > `h264_qsv` > `h264_amf` > `libx264`

Presets are centralized; filter graphs are CPU‑bound (crop/hstack/vstack/scale). Use `--scale-filter` and thread flags to tune throughput and memory.
