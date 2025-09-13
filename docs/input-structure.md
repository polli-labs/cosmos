# COSM Camera Input Directory Structure

This page explains how your input folder should look before running ingest. If your folders follow this pattern, Cosmos can discover clips and process them correctly.

Expected layout
```
input_dir/
 ├── 0H/
 │   ├── 0M/
 │   │   ├── 0S/
 │   │   │   ├── meta.json
 │   │   │   ├── <segment .ts files>
 │   │   ├── 1S/
 │   │   │   ├── meta.json
 │   │   │   ├── <segment .ts files>
 │   │   └── ...
 │   └── 1M/
 │       ├── 0S/
 │       │   ├── meta.json
 │       │   ├── <segment .ts files>
 │       └── ...
 └── LADYBIRD.xml  (your manifest; name may vary)
```

What’s in each folder
- Hour/Minute/Second folders: `NH/MM/SS` hold second‑long segments from the camera.
- Each second folder contains:
  - `meta.json` — frame timing info (start timestamp `x0` and offsets `xi-x0`).
  - `.ts` transport stream files — the encoded frames.
- Manifest (`*.xml`) — lists “clips” with start/end and frame indices. Place it at the top of `input_dir`.

Validate quickly
- Run the interactive ingest self‑test (no processing):
```
cosmos ingest run --yes --dry-run --input-dir /path/to/input --output-dir ./out
```
If a manifest isn’t found, add `--manifest /path/to/manifest.xml`.

Troubleshooting
- Missing `meta.json`: the second folder is incomplete; ingest will skip it.
- No manifest found: pass it explicitly with `--manifest`.
- Mixed structures: ensure the camera’s original hierarchy is preserved (don’t flatten or rename `0H/0M/0S`).

