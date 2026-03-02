---
name: cosmos
description: "Cosmos repo knowledge -- provenance-first video normalization toolkit (ingest/crop/preview/optimize/lineage) with adapter-based ingest and determinism profiles. Inject before modifying cosmos CLI/SDK/provenance or release workflows."
version: "0.2.0"
x:
  source_repo: "cosmos"
  source_branch: "main"
  source_commit: "HEAD"
  package_version: "0.7.0"
  generator: "codex"
  last_modified: "2026-03-02T17:10:00Z"
---

# Cosmos

Cosmos is a provenance-first video normalization toolkit. The CLI/SDK ingests heterogeneous source layouts, generates deterministic web-ready derivatives, and emits machine-joinable sidecars for reproducible downstream automation.

## Quick Facts

- Version: 0.7.0
- Canonical CLI: `cosmos` with root commands `process`, `ingest`, `crop`, `optimize`, `provenance`, `lineage`.
- Back-compat alias: hidden `cosmos pipeline` command still exists; do not use it in new docs/examples.
- SDK entry points: `from cosmos.sdk import ingest, IngestOptions, crop, CropJob, optimize, OptimizeOptions, DeterminismProfile, resolve_profile`.
- Ingest adapter contract: `IngestAdapter` Protocol in `cosmos.ingest.adapter`; built-ins are `cosm` and `generic-media`.
- Determinism profiles: `strict|balanced|throughput` across ingest/crop/optimize.
- Profile precedence: CLI `--profile` > `COSMOS_PROFILE` env > command defaults.
- Lineage: `cosmos lineage {build,upstream,downstream,chain,tree}` and `cosmos.sdk.lineage.LineageIndex`.
- Provenance join key: `view.source.sha256 == clip.output.sha256`.
- ffmpeg resolution order: `COSMOS_FFMPEG` -> `~/.local/share/cosmos/bin/ffmpeg` -> system `PATH`

## Use This Skill When

- Modifying `cosmos/cli/*`, `cosmos/sdk/*`, `cosmos/ffmpeg/*`, `cosmos/crop/*`, `cosmos/ingest/*`, or provenance schemas/emitters.
- Designing or reviewing CLI surfaces (`--json/--plain`, exit mapping, prompt behavior, flag naming).
- Planning release choreography, skill freshness audits, or agent-facing workflows.
- Investigating downstream compatibility and provenance joins.

## Intent Router (Progressive Disclosure)

Load only what you need for the request:

1. Command/API contract questions -> `references/api-surfaces.md`
2. Module ownership/runtime behavior questions -> `references/architecture.md`
3. "How do I run this end-to-end?" -> `references/workflows.md`
4. Cross-repo compatibility or migration risk -> `references/integration-notes.md`
5. Release prep/skill freshness audit -> `references/maintenance-ritual.md`

## First Steps

1. Read `AGENTS.md` in this repo.
2. Use the router above and open only the minimum relevant reference file(s).
3. Capture command-surface receipts for touched surfaces with `uv run cosmos ... --help`.
4. Run quality gate before handoff: `make fmt && make lint && make typecheck && make test`.

## Working Rules

- Keep one CLI (`cosmos`) and one SDK (`cosmos.sdk`) mental model; route business logic through SDK layers.
- Use `cosmos process` as the canonical ingest -> optional crop workflow surface.
- Preserve create-cli contracts: stable flag naming, explicit `--json/--plain`, and non-interactive safety flags (`--yes/--no-input`) on commands that expose prompts.
- Keep explicit user overrides authoritative (for example forced encoder should fail loudly, not silently degrade).
- Preserve crop semantics (`offset_x`/`offset_y` in `[-1, 1]`; rect clamp/even-round behavior).
- Keep provenance contracts and join key stable (`view.source.sha256 == clip.output.sha256`).
- Use shared ffmpeg helpers in `cosmos/ffmpeg/*` rather than shelling ad hoc `ffmpeg`/`ffprobe` commands.

## v0.7.0 Scope Snapshot

- M1 adapter architecture: `IngestAdapter` contract + `cosm`/`generic-media` adapters + auto-detect/override flow.
- M2 lineage graph surfaces: SDK index traversal + CLI query commands for upstream/downstream/chain/tree.
- M3 determinism policy: profile model (`strict|balanced|throughput`) threaded through ingest/crop/optimize and provenance.

## References

- `references/workflows.md` -- canonical agent workflows and copy/paste command recipes.
- `references/api-surfaces.md` -- CLI + SDK contract surfaces and compatibility expectations.
- `references/architecture.md` -- module map and runtime flow.
- `references/integration-notes.md` -- downstream integration and compatibility constraints.
- `references/maintenance-ritual.md` -- required skill freshness process for feature/release work.
- `references/follow-on-issue-drafts.md` -- backlog-ready issue scopes for larger follow-ons.
