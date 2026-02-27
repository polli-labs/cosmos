# Cosmos SDK (Python)

Cosmos exposes a stable SDK for ingest, crop, preview, optimize, and provenance tasks.

## SDK entry points

```python
from cosmos.sdk import (
    ingest,
    IngestOptions,
    crop,
    CropJob,
    optimize,
    OptimizeOptions,
)
```

## Ingest API

```python
from pathlib import Path
from cosmos.sdk.ingest import ingest, IngestOptions

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
```

Notes:

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
    ),
)
```

Optimize behavior and artifacts:

- `mode="auto"` chooses remux unless transform flags imply transcode.
- Auto-selected hardware encoders are runtime-probed; Cosmos falls back to `libx264`
  when a hardware path is unavailable at runtime.
- Run-level artifact: `cosmos_optimize_run.v1.json`
- Output artifact (non-dry-run): `*.mp4.cosmos_optimized.v1.json`
- Dry-run plan: `cosmos_optimize_dry_run.json`

## Provenance helper API

```python
from pathlib import Path
from cosmos.sdk.provenance import sha256_file

sha = sha256_file(Path("clip.mp4"))
```

See [Provenance](provenance.md) for join-key patterns and schema links.

## Error handling notes

- Missing required input paths raise `ValueError` early.
- Dry-runs avoid ffmpeg execution and return planned output paths.
- For real runs, ffmpeg stderr/stdout is persisted in sidecar logs; CLI wrappers map
  failures to non-zero exits while SDK calls return successful outputs only.
