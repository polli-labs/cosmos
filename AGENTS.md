---
title: "Cosmos — Agent/Dev Guide"
doc_type: "agents"
status: "active"
owner: "polli-labs"
last_modified: "2026-03-02T19:01:22.634Z"
last_reviewed: "2026-03-02T19:01:22.634Z"
scope: "repository:cosmos"
---

# Cosmos — Agent/Dev Guide

Repo-specific instructions for `polli-labs/cosmos`.
Keep this file public-safe: no private customer/project context here.

## Canonical model

- One CLI: `cosmos`
- One SDK: `cosmos.sdk`
- One instruction source: `AGENTS.md` (with `CLAUDE.md` as a symlink to `AGENTS.md` when possible)

Cosmos is a provenance-first video normalization toolkit:
- ingest heterogeneous video layouts via adapters
- generate deterministic web-ready derivatives
- emit machine-joinable provenance sidecars

## v0.7.0 command surfaces

- Root commands:
  - `cosmos process` (canonical ingest -> optional crop flow)
  - `cosmos ingest`
  - `cosmos crop`
  - `cosmos optimize`
  - `cosmos provenance`
  - `cosmos lineage`
- Hidden compatibility alias:
  - `cosmos pipeline` (do not use in new docs/workflows)

## Repo map

- `cosmos/sdk/` — canonical business logic entry points
  - `ingest`, `crop`, `optimize`, `preview`, `lineage`, `profiles`, `provenance`
- `cosmos/ingest/` — adapter contract, adapter registry, source-layout-specific behavior
- `cosmos/crop/` — square/rect crop execution and jobs parsing
- `cosmos/preview/` — contact sheet + stacked-overlay preview generation
- `cosmos/ffmpeg/` — ffmpeg/encoder detection and argument builders
- `cosmos/cli/` — Typer app surfaces (thin wrappers over SDK)
- `schema/cosmos/`, `docs/schemas/` — provenance schema contracts
- `skills/cosmos/` — in-repo Cosmos skill package (release-critical)

## Adapter + determinism model

- Ingest adapter contract: `IngestAdapter` in `cosmos.ingest.adapter`
- Built-in adapters:
  - `cosm` (COSM C360)
  - `generic-media` (flat media directories)
- Determinism profiles across ingest/crop/optimize:
  - `strict`, `balanced`, `throughput`
- Profile precedence:
  - CLI `--profile` > `COSMOS_PROFILE` > command defaults

## Provenance invariants

- Run-level sidecars:
  - `cosmos_ingest_run.v1.json`
  - `cosmos_crop_run.v1.json`
  - `cosmos_optimize_run.v1.json`
  - `cosmos_crop_preview_run.v1.json`
- Artifact-level sidecars:
  - `*.mp4.cosmos_clip.v1.json`
  - `*.mp4.cosmos_view.v1.json`
  - `*.mp4.cosmos_optimized.v1.json`
- Join invariant:
  - `view.source.sha256 == clip.output.sha256`
- Lineage surface:
  - `cosmos lineage {build,upstream,downstream,chain,tree}`

## Working rules

- Keep CLI wrappers thin; route behavior through `cosmos/sdk/*`.
- Preserve machine-safe output patterns (`--json`, `--plain`) and stable field names.
- Keep explicit user overrides authoritative (for example forced encoders should fail loudly, not silently degrade).
- Preserve crop semantics:
  - square offsets: `offset_x` / `offset_y` in `[-1, 1]`
  - rect geometry clamp/even-round behavior
- Use shared ffmpeg helpers; avoid ad hoc command construction.

## Release ritual (critical)

Before tagging any release, these are required:

1. **Docs audit**
  - Update affected docs pages and examples for new/changed surfaces.
  - Run `uv run mkdocs build --strict`.
2. **Skill audit**
  - Update `skills/cosmos/SKILL.md` and relevant `skills/cosmos/references/*`.
  - Follow `skills/cosmos/references/maintenance-ritual.md`.
3. **Instruction audit**
  - Refresh this template (`docs/org-kb/agents/templates/repos/cosmos/AGENTS.cosmos.md.mustache`) when behavior changed.
  - Re-render `AGENTS.md` for cosmos and keep `CLAUDE.md` aligned (symlink preferred).
4. **Code quality gate**
  - `make fmt && make lint && make typecheck && make test`.
5. **Receipts**
  - Leave explicit receipts in Linear release/tracker issues (commands, PRs, runs, tags, release URL/assets).

Treat docs + skill + AGENTS/CLAUDE freshness as release-quality requirements, not optional polish.

## Canonical commands

```bash
make fmt && make lint && make typecheck && make test
uv run mkdocs build --strict
uv run cosmos --help
uv run cosmos process --help
uv run cosmos ingest run --help
uv run cosmos crop run --help
uv run cosmos optimize run --help
uv run cosmos lineage --help
```

## Public/private boundary

- Keep this repo’s AGENTS content public-safe.
- If private cosmos integration context is needed, put it in polli monorepo partials (for example under `docs/org-kb/agents/templates/partials/`) and compose it only in private instruction targets.
