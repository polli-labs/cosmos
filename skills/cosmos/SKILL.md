---
name: cosmos
description: "Cosmos repo knowledge -- unified ingest/crop/provenance toolkit for COSM camera media processing, including rectangular crop and ffmpeg bootstrap behavior. Inject before modifying cosmos or planning CLI/provenance/E2E changes."
version: "0.1.0"
x:
  source_repo: "cosmos"
  source_branch: "main"
  source_commit: "HEAD"
  package_version: "0.6.0"
  generator: "claude-code"
  last_modified: "2026-02-27T21:38:44Z"
---

# Cosmos

Unified ingest + post-processing toolkit for video normalization with run-level and artifact-level provenance. Supports multiple source layouts via an adapter contract (COSM C360, generic media, extensible).

## Quick Facts

- Version: 0.6.0
- CLI: `cosmos` (including `cosmos crop ...` surfaces)
- SDK entry points: `from cosmos.sdk import ingest, IngestOptions, crop, CropJob, optimize, OptimizeOptions`
- Ingest adapter contract: `IngestAdapter` Protocol in `cosmos.ingest.adapter` — built-in adapters: `cosm`, `generic-media`. Auto-detected; overridable via `--adapter` CLI flag or `IngestOptions.adapter`.
- Rect crop support: `RectCropJob` + `cosmos crop curated-views`
- Optimize support: `cosmos optimize run` (`auto|remux|transcode`) with run/artifact provenance (`cosmos_optimize_run.v1.json`, `*.cosmos_optimized.v1.json`)
- Optimize auto mode runtime-probes hardware encoders and falls back to `libx264` when unavailable
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

## Contact Sheet Recipes

Generate crop preview contact sheets for curated views:

```bash
cosmos crop curated-views-preview \
  --spec /path/to/spec.json \
  --source-root /path/to/source/root \
  --out /path/to/output \
  --clip-pattern "{date}/8k/{clip}.mp4" \
  --frame start --frame mid --frame end \
  --stack-time 0 \
  --render-max-width 1920 \
  --skip-ffmpeg-check --yes
```

- Frame selectors: `start`, `mid`, `end` for overview; `start+2.0`, `end-1.0` for trim-edge QA.
- The `--clip-pattern` template interpolates `{date}` (ISO→filesystem, e.g. `2025-04-25`→`Apr25`) and `{clip}`.
- Output layout: per-clip bundles with `sheets/sheet_frame_<sel>.png` (contact sheets), `stacked/stacked_t_<sec>.png` (all crops on one frame), `frames/` (raw keyframes), `sheets/_cells/` (individual crop overlays).

Curated views spec JSON (schema `polli-curated-view-spec-v1`):
```json
{
  "schema": "polli-curated-view-spec-v1",
  "views": [{
    "id": "CLIP18_0000-0020_southern-dogface_on_sage",
    "source": {"clip": "CLIP18", "date": "2025-04-25"},
    "trim": {"start_s": 0, "end_s": 20},
    "crop_norm": {"x0": 0.0, "y0": 0.417, "w": 0.399, "h": 0.353},
    "annotations": {"pollinators": [...], "plants": [...]},
    "preprocess": {}
  }]
}
```

## References

- `references/architecture.md` -- module map and runtime flow.
- `references/api-surfaces.md` -- SDK + CLI contracts.
- `references/integration-notes.md` -- downstream integration and compatibility notes.
- `references/maintenance-ritual.md` -- required skill freshness/audit process and standing issue scaffold.
- `references/follow-on-issue-drafts.md` -- ready-to-use issue scopes for CLI redesign, skill ritual, and 8K E2E follow-ons.
