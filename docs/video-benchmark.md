# Video Decode Benchmark

Cosmos includes a developer-facing benchmark harness for the `cosmos.sdk.video`
decode substrate:

```bash
uv run python dev/benchmarks/cosmos_video_decode_benchmark.py
```

When no clips are supplied, the harness generates a small synthetic MP4 fixture
with FFmpeg and writes artifacts under `_work/pol-1185/`. That makes the command
safe on CI and fresh developer machines while still exercising the same SDK
entry points as real WFC clips.

The harness compares these cases:

- `cosmos_ffmpeg_cli`: `COSMOS_VIDEO_BACKEND=ffmpeg-cli`
- `cosmos_pyav`: `COSMOS_VIDEO_BACKEND=pyav`, skipped when `av` or `numpy` is
  not installed
- `cosmos_torchcodec`: `COSMOS_VIDEO_BACKEND=torchcodec`, skipped when `torch`,
  `torchcodec`, `numpy`, or TorchCodec's FFmpeg shared-library requirements are
  unavailable
- `cosmos_auto`: `COSMOS_VIDEO_BACKEND=auto`
- `cosmos_default`: `COSMOS_VIDEO_BACKEND` unset
- `decord_direct`: direct `decord.VideoReader(...).get_batch(...)`, skipped
  when `decord` or `numpy` is not installed

Backend selection is scoped per benchmark case, and the script restores the
previous `COSMOS_VIDEO_BACKEND` value after each run.

## Current Decision Posture

Treat Decord as an external Linux comparator and parity guardrail, not as a
Cosmos runtime dependency. The benchmark harness exists so backend decisions are
made from the same correctness, timing, host-fact, and availability matrix.

The current default remains `ffmpeg-cli`. PyAV is useful for explicit portability
and macOS experiments, but it is not the Linux performance answer based on the
POL-1175/POL-1176 benchmark work. TorchCodec is the most promising maintained
library candidate, but it remains explicit opt-in until representative WFC clips
pass the benchmark gate in an environment with managed FFmpeg shared libraries.

Do not promote a backend into `COSMOS_VIDEO_BACKEND=auto` from synthetic results
alone. Default-backend changes should be justified by representative WFC clips,
preserved request order and duplicate semantics, bounded pixel deltas, and a
clear missing-backend failure policy. Tensor-native APIs are also deferred until
a backend demonstrates a real advantage that is lost when Cosmos materializes
public `RgbFrame.rgb24` bytes.

PyNvVideoCodec/NVDEC is currently a hold rather than a rejection. On the current
blade posture, the wheel requires NVIDIA encode libraries such as
`libnvidia-encode.so.1` at import time even for decode-oriented exploration, so
it is not a benchmark case here until host runtime policy changes.

## Real Clips

Pass WFC or other representative clips explicitly:

```bash
uv run python dev/benchmarks/cosmos_video_decode_benchmark.py \
  --clip /data/wfc/CLIP17_0000-0015_unidentified-fly-or-bee_on_parsley.mp4 \
  --clip /data/wfc/CLIP18_0000-0020_southern-dogface_on_sage.mp4 \
  --out-dir _work/pol-1185/wfc-real
```

Or scan a directory:

```bash
uv run python dev/benchmarks/cosmos_video_decode_benchmark.py \
  --input-dir /data/wfc \
  --glob "*.mp4" \
  --out-dir _work/pol-1185/wfc-real
```

Default request patterns mirror the POL-1155/POL-1175 benchmark shapes:

- `dense_stride`
- `late_single`
- `late_pair`
- `split_sparse`
- `random_sparse`
- `duplicate_order_smoke` for request-order and duplicate-index checks

For long clips, `--dense-max-indices` caps the dense request count. Use
`--dense-max-indices 0` to disable the cap.

## Optional Dependencies

Base development setup is enough for the FFmpeg CLI, `auto`, and unset-default
Cosmos cases:

```bash
uv sync --extra dev --locked
```

To include the PyAV-backed Cosmos case:

```bash
uv sync --extra dev --extra video-av --locked
```

To include the CPU TorchCodec-backed Cosmos case:

```bash
uv sync --extra dev --extra video-torchcodec --locked
```

TorchCodec uses FFmpeg shared libraries at import time. On Linux, a static
`ffmpeg` binary on `PATH` is not sufficient; install matching shared FFmpeg
libraries or make them visible with `LD_LIBRARY_PATH` before running the
benchmark.

Decord is an external comparator, not a Cosmos runtime dependency. For a
one-off benchmark with Decord available in the `uv run` environment:

```bash
uv run --with decord --with numpy \
  python dev/benchmarks/cosmos_video_decode_benchmark.py
```

On Linux, `COSMOS_VIDEO_BACKEND=auto` intentionally stays on the FFmpeg CLI
backend. On macOS, `auto` may try PyAV first and fall back to FFmpeg CLI only
when the optional backend is unavailable. Keep `ffmpeg` and `ffprobe` available
on `PATH`, or use `COSMOS_FFMPEG` / `COSMOS_FFPROBE` to point Cosmos at specific
binaries.

## Outputs

Each run writes:

- `cosmos_video_decode_benchmark.v1.json`
- `cosmos_video_decode_timings.csv`
- `cosmos_video_decode_correctness.csv`
- `cosmos_video_decode_summary.md`

The JSON output includes environment metadata, clip metadata, explicit request
patterns, backend availability and package versions, per-repeat timings,
correctness checks, frame digests, and raw artifact paths. Correctness covers
frame counts, shapes, request order, duplicate payload identity, exact frame
matches, max absolute RGB deltas, and mean absolute RGB deltas against the best
available reference backend.
