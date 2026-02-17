---
name: cosmos
description: "Cosmos repo knowledge -- unified ingest/crop/provenance toolkit for COSM camera media processing, including rectangular crop and ffmpeg bootstrap behavior. Inject before modifying cosmos or planning CLI/provenance/E2E changes."
version: "0.1.0"
x:
  source_repo: "cosmos"
  source_branch: "main"
  source_commit: "2929d18"
  package_version: "0.4.0"
  generator: "codex"
  last_modified: "2026-02-13T00:00:00Z"
---

# Cosmos

Unified ingest + post-processing toolkit for COSM camera outputs with run-level and artifact-level provenance.

## Quick Facts

- Version: 0.4.0
- CLIs: `cosmos` and `squarecrop`
- SDK entry points: `from cosmos.sdk import ingest, IngestOptions, crop, CropJob`
- Rect crop support: `RectCropJob` + `cosmos crop curated-views`
- Preview support: `cosmos crop preview` + `cosmos crop curated-views-preview` emitting `cosmos_crop_preview_run.v1.json` and per-clip `preview_plan.v1.json` bundles
- ffmpeg resolution order: `COSMOS_FFMPEG` -> `~/.local/share/cosmos/bin/ffmpeg` -> system `PATH`

## Use This Skill When

- Modifying `cosmos/cli/*`, `cosmos/sdk/*`, `cosmos/ffmpeg/*`, `cosmos/crop/*`, or provenance schema/emitters.
- Planning CLI redesign, release changes, or E2E policy updates.
- Investigating downstream compatibility with provenance artifacts.

## First Steps

1. Read `AGENTS.md` in this repo.
2. Review `references/api-surfaces.md` for current command/API contracts.
3. Review `references/maintenance-ritual.md` before finalizing feature work or release prep.
4. Run quality gate before handoff: `make fmt && make lint && make typecheck && make test`.

## Working Rules

- Route business logic through `cosmos/sdk/*`; keep CLI layers thin.
- Preserve square-crop offset semantics (`offset_x`/`offset_y` in `[-1, 1]`).
- Keep preview geometry parity with crop execution math (rect clamp/even-round behavior, square offset/center semantics).
- Keep provenance join key stable: `view.source.sha256 == clip.output.sha256`.
- Use shared ffmpeg helpers in `cosmos/ffmpeg/*` instead of hardcoded `ffmpeg`/`ffprobe` commands.
- Keep interactive prompts behind TTY-safe CLI boundaries (`--yes` and `--skip-ffmpeg-check` for non-interactive runs).

## References

- `references/architecture.md` -- module map and runtime flow.
- `references/api-surfaces.md` -- SDK + CLI contracts.
- `references/integration-notes.md` -- downstream integration and compatibility notes.
- `references/maintenance-ritual.md` -- required skill freshness/audit process and standing issue scaffold.
- `references/follow-on-issue-drafts.md` -- ready-to-use issue scopes for CLI redesign, skill ritual, and 8K E2E follow-ons.
