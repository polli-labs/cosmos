# Cosmos

Unified ingest and post-processing toolkit for COSM camera media.

Cosmos is designed for both interactive operators and automation:

- `cosmos` CLI for ingest/crop/optimize/provenance workflows
- `squarecrop` CLI for standalone crop operations
- `cosmos.sdk` for stable Python integration
- run-level and artifact-level provenance sidecars for reproducibility

## Documentation

- Docs home: https://docs.polli.ai/cosmos/
- CLI reference: [docs/cosmos-cli.md](docs/cosmos-cli.md)
- SDK reference: [docs/sdk.md](docs/sdk.md)
- Provenance guide: [docs/provenance.md](docs/provenance.md)
- Encoder behavior matrix: [docs/encoder-behavior.md](docs/encoder-behavior.md)

## Agent skill (recommended for agent operators)

Cosmos keeps a canonical in-repo skill package that should be consulted before
changing CLI, SDK, ffmpeg policy, provenance fields, or release behavior.

- Entrypoint: [skills/cosmos/SKILL.md](skills/cosmos/SKILL.md)
- API contracts: [skills/cosmos/references/api-surfaces.md](skills/cosmos/references/api-surfaces.md)
- Maintenance ritual: [skills/cosmos/references/maintenance-ritual.md](skills/cosmos/references/maintenance-ritual.md)

## Install

- Production: `pip install polli-cosmos`
- Development (uv):

```bash
uv venv .venv
. .venv/bin/activate
uv pip install -e ".[dev]"
```

## CLI quickstart

```bash
cosmos --help
cosmos ingest run --help
cosmos crop run --help
cosmos optimize run --help
cosmos crop preview --help
squarecrop --help
```

## Common workflows

### 1) Ingest camera outputs

```bash
make run.ingest IN=/path/to/raw OUT=./out YES=1
```

### 2) Crop MP4 views with jobs JSON

```bash
make run.crop INPUT=/path/to/clip.mp4 OUT=_work/out JOBS=_work/job.json YES=1
```

### 3) Generate crop previews (contact sheets + stacked overlays)

```bash
cosmos crop preview \
  --input /path/to/clip.mp4 \
  --jobs-file _work/job.json \
  --out _work/preview \
  --frame start --frame mid \
  --stack-time 0 \
  --yes
```

### 4) Optimize MP4s for web delivery

```bash
# Faststart remux (default mode=auto, no transform flags)
cosmos optimize run --input /path/to/clip.mp4 --out-dir _work/web --yes

# Explicit transcode
cosmos optimize run \
  --input /path/to/clip.mp4 \
  --out-dir _work/web \
  --mode transcode \
  --target-height 1080 --fps 30 --crf 23 \
  --yes
```

### 5) Inspect provenance mapping

```bash
make run.provenance DIR=_work/out
```

## Crop jobs semantics

Squarecrop jobs accept either offsets or centers:

- Recommended: `offset_x`, `offset_y` in `[-1, 1]` relative to available margin
  - `0` is centered
  - positive values move right/down
  - negative values move left/up
- Alternative: `center_x`, `center_y` in `[0, 1]`
- Do not combine offsets and centers in a single job.

Other common fields:

- `targets`: one or more square output sizes
- `trim_unit: "time"`, `trim_start`, `trim_end` for bounded crops

## Provenance and stable IDs

- Clip IDs: `clip-<stem>-<sha8>`
- View IDs: `view-<stem>-<sha8>`
- Optimize sidecars: `*.mp4.cosmos_optimized.v1.json`

Core join behavior:

- `view.source.sha256 == clip.output.sha256`

See [docs/provenance.md](docs/provenance.md) for full schema links and examples.

## Encoder policy (cross-platform)

- macOS: `h264_videotoolbox` -> `libx264`
- Linux: `h264_nvenc` -> `h264_qsv` -> `h264_vaapi` -> `libx264`
- Windows: `h264_nvenc` -> `h264_qsv` -> `h264_amf` -> `libx264`

Cosmos runtime-probes auto-selected hardware encoders and falls back to `libx264`
if the host advertises an encoder that is not actually usable.

## Developer workflow

```bash
make uv-sync
make fmt
make lint
make typecheck
make test
```

## Optional local E2E lanes

- Slim ingest repro: `make e2e-repro-slim`
- 8K windowed repro: `make e2e-repro-8k`
- Full heavy repro: `make e2e-repro-full`

These are fixture-gated and intentionally off for standard CI.
