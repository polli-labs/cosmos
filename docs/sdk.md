# Cosmos SDK (Python)

Cosmos exposes a stable SDK for video probe/decode, ingest, crop, preview, optimize, and
provenance tasks.

## SDK entry points

```python
from cosmos.sdk import (
    ingest,
    IngestOptions,
    crop,
    CropJob,
    optimize,
    OptimizeOptions,
    probe_video,
    extract_frames_at_indices,
    extract_frames_at_times,
    DeterminismProfile,
    resolve_profile,
)
```

## Video probe/decode API

```python
from pathlib import Path
from cosmos.sdk.video import probe_video, extract_frames_at_indices, extract_frames_at_times

source = Path("clip.mp4")
probe = probe_video(source)
frames = extract_frames_at_indices(source, [0, 10])
time_frames = extract_frames_at_times(source, [0.0, 2.5])
```

Video substrate behavior:

- `probe_video()` returns typed metadata for the first video stream, including dimensions,
  duration/fps/frame count when ffprobe reports them, codec names, and source path.
- Frame extraction returns `RgbFrame` objects with source/request metadata and raw `rgb24`
  bytes. Cosmos does not return NumPy arrays or PIL images from this public contract.
- Sparse index extraction batches unique requested indices into one FFmpeg pass, then
  returns frames in the caller's requested order, including duplicate indices.
- For late or widely separated sparse index requests, Cosmos may use cached ffprobe packet
  timestamps to seek into smaller FFmpeg decode windows. Dense requests still use the single
  full-scan batch path when that is cheaper.
- The default backend remains `ffmpeg-cli` for stable byte output through the system/shared
  FFmpeg stack. Install `polli-cosmos[video-av]` and set
  `COSMOS_VIDEO_BACKEND=pyav` to exercise the optional in-process PyAV backend. Install
  `polli-cosmos[video-torchcodec]` and set `COSMOS_VIDEO_BACKEND=torchcodec` to exercise
  the optional CPU TorchCodec backend. `COSMOS_VIDEO_BACKEND=auto` is still
  platform-aware: it uses PyAV with FFmpeg CLI fallback on macOS and keeps FFmpeg CLI on
  Linux.
- PyAV uses the wheel's bundled libav stack; decoded RGB bytes may differ slightly from
  system FFmpeg output even when decoded frame indices are preserved. Treat it as an
  explicit performance backend until downstream tolerance and Linux benchmarks approve it.
- TorchCodec returns PyTorch tensors internally, but Cosmos converts them back to the
  public `RgbFrame.rgb24` byte contract. TorchCodec also needs compatible PyTorch,
  TorchCodec, NumPy, and FFmpeg shared-library installs; a working `ffmpeg` executable by
  itself is not enough when the shared libraries are unavailable to the dynamic loader.
- Binary resolution follows the shared Cosmos ffmpeg/ffprobe policy (`COSMOS_FFMPEG`,
  `COSMOS_FFPROBE`, managed binaries, then system PATH).

## Ingest API

```python
from pathlib import Path
from cosmos.sdk.ingest import ingest, IngestOptions

# COSM ingest (auto-detected from manifest XML)
outputs = ingest(
    input_dir=Path("/data/cosm"),
    output_dir=Path("./out"),
    manifest=None,
    options=IngestOptions(
        width=3840,
        height=2160,
        quality_mode="balanced",
        clips=["CLIP1", "CLIP2"],
        scale_filter="bicubic",
        filter_threads=2,
        filter_complex_threads=2,
        decode="auto",
        window_seconds=None,
        dry_run=False,
    ),
)

# Generic media ingest (auto-detected from video files)
outputs = ingest(
    input_dir=Path("/data/field-videos"),
    output_dir=Path("./out"),
    options=IngestOptions(adapter="generic-media"),
)
```

Notes:

- The `adapter` field selects the source layout adapter (`"cosm"`, `"generic-media"`). When `None` (default), the adapter is auto-detected from directory contents.
- `dry_run=True` writes `cosmos_dry_run.json` (planned commands and clip plan).
- Real runs produce `{clip}.mp4.cmd.txt` and `{clip}.mp4.log.txt` alongside outputs.
- `clips=[...]` restricts ingest to a subset by clip name.

## Crop API

```python
from pathlib import Path
from cosmos.sdk.crop import crop, CropJob

outputs = crop(
    input_videos=[Path("clip.mp4")],
    jobs=[CropJob(size=1080, center_x=0.5, center_y=0.5, start=0.0, end=10.0)],
    out_dir=Path("./crops"),
    ffmpeg_opts={"dry_run": False},
)
```

Jobs files:

```python
from pathlib import Path
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.crop import crop

jobs = parse_jobs_json(Path("job_settings.json"))
outputs = crop([Path("clip.mp4")], jobs, Path("./crops"))
```

## Crop preview API

```python
from pathlib import Path
from cosmos.crop.jobs import parse_jobs_json
from cosmos.sdk.preview import RenderOptions, preview

jobs = parse_jobs_json(Path("jobs.json"))
result = preview(
    input_videos=[Path("clip.mp4")],
    jobs=jobs,
    out_dir=Path("./preview"),
    options=RenderOptions(
        frame_selectors=["start", "mid"],
        stack_times_sec=[0.0, 12.5],
        render_max_width=1600,
        grid_step_px=400,
        show_rulers=True,
        alpha=0.25,
    ),
)
print(result.run_path)
```

Preview outputs:

- `cosmos_crop_preview_run.v1.json`
- per-clip bundle with `preview_plan.v1.json`, `frames/`, `sheets/`, and `stacked/`

## Optimize API

```python
from pathlib import Path
from cosmos.sdk.optimize import optimize, OptimizeOptions

outputs = optimize(
    input_videos=[Path("clip.mp4")],
    out_dir=Path("./web"),
    options=OptimizeOptions(
        mode="auto",         # auto|remux|transcode
        target_height=1080,   # optional
        fps=30.0,             # optional
        crf=23,               # optional (transcode)
        faststart=True,
        suffix="_optimized",
        dry_run=False,
        profile="strict",    # optional: strict|balanced|throughput
    ),
)
```

Optimize behavior and artifacts:

- `mode="auto"` chooses remux unless transform flags imply transcode.
- Auto-selected hardware encoders are runtime-probed; Cosmos falls back to `libx264`
  when a hardware path is unavailable at runtime.
- `profile` activates a determinism profile (`strict`, `balanced`, `throughput`). The
  `strict` profile pins `libx264`, 4 threads, and bitexact flags for cross-host reproducibility.
  Per-field overrides (e.g. `encoder=`) always take precedence over profile defaults.
- Run-level artifact: `cosmos_optimize_run.v1.json`
- Output artifact (non-dry-run): `*.mp4.cosmos_optimized.v1.json`
- Dry-run plan: `cosmos_optimize_dry_run.json`

## Lineage graph API

```python
from pathlib import Path
from cosmos.sdk.lineage import build_index

index = build_index(Path("./outputs"))

# Upstream ancestors of a given artifact
ancestors = index.upstream("abc123...")

# Downstream derivatives
derivatives = index.downstream("abc123...")

# Full chain (upstream + self + downstream)
chain = index.chain("abc123...")

# Nested tree dict (upstream direction)
tree = index.tree("abc123...")

# Serialize to JSON
index.write(Path("lineage.json"))
```

The lineage index scans `*.cosmos_clip.v1.json`, `*.cosmos_view.v1.json`, and
`*.cosmos_optimized.v1.json` sidecars recursively. Nodes are keyed by `output.sha256`
and edges are derived from `source.sha256` join keys.

## Provenance helper API

```python
from pathlib import Path
from cosmos.sdk.provenance import sha256_file

sha = sha256_file(Path("clip.mp4"))
```

See [Provenance](provenance.md) for join-key patterns and schema links.

## Error handling notes

- Missing required input paths raise `ValueError` early.
- Video probe/decode helpers raise `VideoProbeError` or `VideoDecodeError` with ffmpeg/ffprobe
  stderr when tool execution fails.
- Dry-runs avoid ffmpeg execution and return planned output paths.
- For real runs, ffmpeg stderr/stdout is persisted in sidecar logs; CLI wrappers map
  failures to non-zero exits while SDK calls return successful outputs only.
