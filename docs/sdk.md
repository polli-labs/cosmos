# Cosmos SDK (Python)

Cosmos exposes a small, stable SDK for programmatic ingest and cropping. This page covers the main entry points and options.

## Ingest API

Function
```python
from pathlib import Path
from cosmos.sdk.ingest import ingest, IngestOptions

outputs: list[Path] = ingest(
    input_dir=Path("/data/cosm"),
    output_dir=Path("./out"),
    manifest=None,  # or Path("/data/cosm/LADYBIRD.xml")
    options=IngestOptions(
        width=3840,
        height=2160,
        quality_mode="balanced",   # quality|balanced|performance|low_memory|minimal
        low_memory=False,
        crf=None,
        clips=["CLIP1", "CLIP2"], # process a subset by name
        dry_run=False,
        scale_filter="bicubic",    # lanczos|spline36|bicubic|bilinear
        filter_threads=2,
        filter_complex_threads=2,
        decode="auto",             # auto|hw|sw (best-effort)
        window_seconds=None,        # limit duration for previews
    ),
)
```

Notes
- When `dry_run=True`, `ingest` writes `cosmos_dry_run.json` describing encoder preference, filter graph, and clip plan.
- For transparency, each output clip includes `{clip}.mp4.cmd.txt` and `{clip}.mp4.log.txt`.
- Use `clips=[...]` to process only specific clips.

## Crop API (squarecrop)

Data model
```python
from dataclasses import dataclass

@dataclass
class CropJob:
    center_x: float = 0.5
    center_y: float = 0.5
    size: int = 1080
    start: float | None = None
    end: float | None = None
```

Functions
```python
from pathlib import Path
from cosmos.sdk.crop import crop, CropJob

outputs = crop(
    input_videos=[Path("clip.mp4")],
    jobs=[CropJob(size=640, center_x=0.55, center_y=0.5, start=0.0, end=10.0)],
    out_dir=Path("./crops"),
    ffmpeg_opts={"dry_run": False},
)
```

Jobs files
```python
from cosmos.crop.jobs import parse_jobs_json
jobs = parse_jobs_json(Path("job_settings.json"))
outputs = crop([Path("clip.mp4")], jobs, Path("./crops"))
```

## Crop Preview API

Functions
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

Preview outputs
- Run-level artifact: `cosmos_crop_preview_run.v1.json`
- Per-clip bundle:
  - `preview_plan.v1.json` (resolved geometry/time contract)
  - `frames/*.png`
  - `sheets/sheet_frame_<selector>.png`
  - `stacked/stacked_t_<time>.png`

## Error handling
- Ingest raises `ValueError` if the input folder is missing.
- Under dry‑run, `ingest` returns planned output paths; no ffmpeg errors are raised.
- During real runs, ffmpeg failures are captured into `{clip}.mp4.log.txt` and surfaced as a failed result in CLI; the SDK returns paths for successful clips only.
