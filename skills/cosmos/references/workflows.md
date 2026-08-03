# Cosmos Workflows (Agent-Ready)

Copy/paste workflows for common agent tasks. Prefer these canonical paths over ad hoc command composition.

## 1) Command surface receipts

Use this whenever CLI surface changes are in scope:

```bash
cd /home/caleb/repo/cosmos
uv run cosmos --help
uv run cosmos process --help
uv run cosmos ingest run --help
uv run cosmos crop run --help
uv run cosmos optimize run --help
uv run cosmos lineage --help
```

## 2) Ingest generic media (deterministic dry run)

```bash
cd /home/caleb/repo/cosmos
uv run cosmos ingest run \
  --input-dir /path/to/videos \
  --output-dir /path/to/out \
  --adapter generic-media \
  --profile strict \
  --dry-run \
  --skip-ffmpeg-check \
  --yes \
  --json
```

## 3) Ingest COSM layout (auto adapter)

```bash
cd /home/caleb/repo/cosmos
uv run cosmos ingest run \
  --input-dir /path/to/cosm/raw \
  --output-dir /path/to/cosm/normalized \
  --profile balanced \
  --clip CLIP01 \
  --clip CLIP02 \
  --skip-ffmpeg-check \
  --yes \
  --plain
```

## 4) End-to-end canonical flow (`cosmos process`)

Ingest and optionally crop in one command:

```bash
cd /home/caleb/repo/cosmos
uv run cosmos process /path/to/raw /path/to/out \
  --post-process \
  --crop-config /path/to/jobs.json \
  --profile strict \
  --skip-ffmpeg-check \
  --yes \
  --json
```

Notes:
- Use `cosmos process` in new docs/automation.
- `cosmos pipeline` is retired; do not use it.
- `process --dry-run --json` writes `cosmos_process_dry_run.v1.json` and
  child ingest stage dry-run artifacts.

## 5) Optimize derivatives for web delivery

```bash
cd /home/caleb/repo/cosmos
uv run cosmos optimize run \
  --input /path/to/clip01.mp4 \
  --input /path/to/clip02.mp4 \
  --out-dir /path/to/optimized \
  --mode auto \
  --target-height 1080 \
  --fps 30 \
  --profile throughput \
  --skip-ffmpeg-check \
  --yes \
  --json
```

Profile precedence:
- `--profile` CLI option
- `COSMOS_PROFILE` environment variable
- command defaults

## 6) Build and query lineage graph

```bash
cd /home/caleb/repo/cosmos
uv run cosmos lineage build /path/to/out /path/to/optimized --output /tmp/lineage.json --json
uv run cosmos lineage upstream 5c4f7c1 --in /path/to/out --in /path/to/optimized --json
uv run cosmos lineage downstream 5c4f7c1 --in /path/to/out --in /path/to/optimized --json
uv run cosmos lineage chain 5c4f7c1 --in /path/to/out --in /path/to/optimized --plain
```

Identifiers may be full sha256, sha prefix, or artifact IDs.

## 7) Curated-view preview contact sheets

```bash
cd /home/caleb/repo/cosmos
uv run cosmos crop curated-views-preview \
  --spec /path/to/spec.json \
  --source-root /path/to/source/root \
  --out /path/to/preview \
  --clip-pattern "{date}/8k/{clip}.mp4" \
  --frame start \
  --frame mid \
  --frame end \
  --stack-time 0 \
  --render-max-width 1920 \
  --skip-ffmpeg-check \
  --yes
```

## 8) Probe exact decoded-frame identities

Use the integer PTS ticks and stream time base when an experiment, annotation,
or provenance record must bind to exact decoded frames:

```python
from fractions import Fraction

from cosmos.sdk import probe_video_timeline

timeline = probe_video_timeline("clip.mp4")
frame_index = 756
pts_tick = timeline.pts_ticks[frame_index]
exact_seconds = Fraction(
    pts_tick * timeline.time_base_numerator,
    timeline.time_base_denominator,
)
```

The ticks are literal ffprobe frame `pts`. Do not replace this join with nominal
FPS arithmetic, rounded seconds, sorted packet timestamps, or estimated
timestamps. Timeline probing fails closed when ffprobe cannot provide a
strictly increasing integral `pts` identity for every decoded frame.

For unattended work that needs a subprocess bound, set positive finite seconds
at invocation time:

```bash
COSMOS_VIDEO_FFMPEG_TIMEOUT=120 uv run python your_video_job.py
```

## 9) Pre-release gate (skill + code freshness)

From the repository root:

```bash
make fmt && make lint && make typecheck && make test
uv run mkdocs build --strict
```

## 10) Video decode backend benchmark

Use this when comparing `cosmos.sdk.video` backends or checking whether Decord
can be removed from a downstream Linux path. From the repository root:

```bash
uv run python dev/benchmarks/cosmos_video_decode_benchmark.py \
  --out-dir _work/pol-1185/synthetic-smoke
```

Pass real WFC clips explicitly when they are available:

```bash
uv run python dev/benchmarks/cosmos_video_decode_benchmark.py \
  --clip /path/to/CLIP17_0000-0015_unidentified-fly-or-bee_on_parsley.mp4 \
  --clip /path/to/CLIP18_0000-0020_southern-dogface_on_sage.mp4 \
  --out-dir _work/pol-1185/wfc-real
```

Optional comparators:

```bash
uv sync --extra dev --extra video-av --locked
uv sync --extra dev --extra video-torchcodec --locked
uv run --with decord --with numpy python dev/benchmarks/cosmos_video_decode_benchmark.py
```

Decision rule: synthetic smoke output proves the harness and backend availability,
not default-backend readiness. Keep Decord as an external Linux comparator until
a maintained backend passes representative WFC clips with preserved order,
duplicate semantics, acceptable pixel deltas, and stable missing-backend errors.
TorchCodec needs FFmpeg shared libraries visible to the dynamic loader; a static
`ffmpeg` executable on `PATH` is not enough for that backend. PyNvVideoCodec/NVDEC
is out of the default benchmark path until host runtime policy provides the NVIDIA
encode libraries required by its wheel at import time.

Primary artifacts:

- `cosmos_video_decode_benchmark.v1.json`
- `cosmos_video_decode_timings.csv`
- `cosmos_video_decode_correctness.csv`
- `cosmos_video_decode_summary.md`
