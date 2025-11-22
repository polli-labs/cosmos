# Changelog

All notable changes to this project will be documented in this file.

## 0.3.0 — Provenance + squarecrop offsets (2025-11-21)
- Add JSON Schemas and SDK models for provenance: ingest_run.v1.json, clip.v1.json, crop_run.v1.json, view.v1.json.
- Emit provenance on ingest (per-clip) and crop (per-view). Add `cosmos provenance` CLI for quick lookups.
- Squarecrop: implement legacy CENTER_TARGET offset semantics (offset_x/offset_y relative to available margin). Jobs parser now accepts `offset_x/offset_y` or absolute `center_x/center_y`.
- Docs: new Provenance page and linked Schemas; clarify squarecrop offset semantics and jobs fields.
- CI: cross‑platform fixes (Windows venv activation, mypy/Ruff lint fixes), stable tests under patched `os.name`.
- Provenance now includes duration/fps/width_px/height_px and stable clip/view ids; crop artifacts record offsets/trim info for easier downstream introspection.

## 0.2.0 — Docs hosting + branding (2025-09-14)
- MkDocs + Material theme; docs workflow deploys to docs.polli.ai/cosmos via rsync.
- Initial branding plan stub; future integration with @polli/ui brand kit.

## 0.1.0 — Initial scaffold
- Monorepo layout with `cosmos` package (no src/)
- Two CLIs: `cosmos`, `squarecrop`
- SDK stubs for ingest and crop
- FFmpeg helpers, docs, CI, and GitHub templates
