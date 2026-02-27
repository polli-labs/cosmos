# COSM Camera Input Structure

Cosmos ingest expects the original COSM camera hierarchy and manifest layout.

## Expected directory shape

```text
input_dir/
  0H/
    0M/
      0S/
        meta.json
        <segment .ts files>
      1S/
        meta.json
        <segment .ts files>
      ...
    1M/
      0S/
        meta.json
        <segment .ts files>
      ...
  LADYBIRD.xml
```

## Required files

- `meta.json` in each second folder (`.../SS/`)
- `.ts` transport stream segments in each second folder
- a top-level `*.xml` manifest (or pass one explicitly via `--manifest`)

## Quick validation

```bash
cosmos ingest run --input-dir /path/to/input --output-dir ./out --dry-run --yes
```

If manifest discovery fails, run with an explicit manifest path:

```bash
cosmos ingest run --input-dir /path/to/input --output-dir ./out --manifest /path/to/LADYBIRD.xml --dry-run --yes
```

## Common issues

- Missing `meta.json`: the second folder is incomplete and may be skipped.
- Flattened directory layout: restore the `H/M/S` hierarchy.
- Wrong manifest location: keep it at the root of `input_dir` or pass `--manifest`.
