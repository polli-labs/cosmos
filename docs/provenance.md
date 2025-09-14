# Provenance (v1)

Cosmos emits machine‑readable JSON artifacts that record how media was produced. These files enable strict reproducibility and downstream analytics in Ibrida.

- Run‑level:
  - `cosmos_ingest_run.v1.json` – ingest environment, encoder preference, options
  - `cosmos_crop_run.v1.json` – crop jobs, environment
- Artifact‑level (next to each MP4):
  - `*.mp4.cosmos_clip.v1.json` – ingest output (dimensions, fps, sha256, encoder)
  - `*.mp4.cosmos_view.v1.json` – squarecrop output (source sha256, output sha256, crop spec)

## Join keys

- `CropView.source.sha256` = `ClipArtifact.output.sha256` – stable link from ingest → crop
- `ClipArtifact.ingest_run_id` and `CropView.crop_run_id` – join to respective run files

## Schemas

- Ingest run: [schemas/ingest_run.v1.json](schemas/ingest_run.v1.json)
- Clip artifact: [schemas/clip.v1.json](schemas/clip.v1.json)
- Crop run: [schemas/crop_run.v1.json](schemas/crop_run.v1.json)
- View artifact: [schemas/view.v1.json](schemas/view.v1.json)

## Example (clip artifact)

```json
{
  "$schema": "https://docs.polli.ai/cosmos/schemas/clip.v1.json",
  "schema_version": "1.0.0",
  "clip_id": "clip_…",
  "ingest_run_id": "ing_…",
  "name": "CLIP1",
  "output": {"path": "clips/CLIP1.mp4", "sha256": "…", "bytes": 12345678},
  "video": {"width": 4096, "height": 2160, "fps": 29.97, "pix_fmt": "yuv420p", "color_space": "bt709"},
  "encode": {"impl": "h264_nvenc", "crf": 18, "filtergraph": "…"},
  "env": {"ffmpeg": {"version": "ffmpeg 6.1.1 …"}, "system": {"os": "macOS 14.6 …"}}
}
```

## SDK helpers

```python
from pathlib import Path
from cosmos.sdk.provenance import sha256_file

sha = sha256_file(Path("clips/CLIP1.mp4"))
# Match against crop views by source.sha256 or against clip artifacts by output.sha256
```

Tips:
- Per‑file artifacts are siblings of the MP4; copy them together for full provenance.
- Dry‑runs only emit run‑level JSON; artifact files require real outputs.
