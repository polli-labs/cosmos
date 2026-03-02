# Lineage Graph

Cosmos builds a directed acyclic graph (DAG) from provenance sidecar artifacts
to answer upstream/downstream questions across ingest, crop, and optimize stages.

## How it works

The lineage index is built deterministically by scanning directories for provenance
sidecar files:

- `*.cosmos_clip.v1.json` — ingest stage nodes
- `*.cosmos_view.v1.json` — crop stage nodes
- `*.cosmos_optimized.v1.json` — optimize stage nodes

Nodes are keyed by their `output.sha256` hash. Edges are derived from `source.sha256`
join keys, linking each artifact to its upstream source.

## CLI usage

### Build an index

```bash
cosmos lineage build /path/to/outputs --json
cosmos lineage build /path/to/outputs --output lineage.json
```

### Query upstream ancestors

```bash
cosmos lineage upstream <sha256-or-id> --in /path/to/outputs --json
```

### Query downstream derivatives

```bash
cosmos lineage downstream <sha256-or-id> --in /path/to/outputs --json
```

### Full chain traversal

```bash
cosmos lineage chain <sha256-or-id> --in /path/to/outputs --json
```

### Nested source tree

```bash
cosmos lineage tree <sha256-or-id> --in /path/to/outputs --json
```

## Identifier resolution

All query commands accept artifact identifiers in three forms:

1. **Full sha256** — exact match on `output.sha256`
2. **sha256 prefix** — unambiguous prefix match (e.g., first 8 characters)
3. **Artifact ID** — e.g., `clip-CLIP1-abc12345`, `view-VIEW1-def67890`

## SDK usage

```python
from pathlib import Path
from cosmos.sdk.lineage import build_index

index = build_index(Path("./outputs"))

# Query
ancestors = index.upstream("abc123...")
derivatives = index.downstream("abc123...")
chain = index.chain("abc123...")
tree = index.tree("abc123...")

# Serialize
index.write(Path("lineage.json"))
d = index.to_dict()  # {"schema": "cosmos-lineage-index-v1", ...}
```

## Output modes

All CLI commands support three output modes:

| Flag | Mode | Description |
|------|------|-------------|
| (default) | human | Formatted output to stdout, diagnostics to stderr |
| `--json` | json | Structured JSON payload to stdout |
| `--plain` | plain | Tab-delimited lines to stdout |

## JSON schema

The lineage index uses the `cosmos-lineage-index-v1` schema:

```json
{
  "schema": "cosmos-lineage-index-v1",
  "node_count": 3,
  "edge_count": 2,
  "nodes": [
    {"id": "clip-CLIP1-abc12345", "stage": "ingest", "sha256": "...", "path": "...", "sidecar": "..."},
    {"id": "view-VIEW1-def67890", "stage": "crop", "sha256": "...", "path": "...", "sidecar": "..."},
    {"id": "optimized-OPT1-ghi12345", "stage": "optimize", "sha256": "...", "path": "...", "sidecar": "..."}
  ],
  "edges": [
    {"source": "<clip-sha256>", "target": "<view-sha256>"},
    {"source": "<view-sha256>", "target": "<optimized-sha256>"}
  ],
  "warnings": []
}
```
