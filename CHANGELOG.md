# Changelog

All notable changes to this project will be documented in this file.

## 0.3.4 — Duration-correct crop trimming + skill governance bootstrap (2026-02-16)
- Fix crop trimming args in `cosmos/ffmpeg/args.py`: use `-t (end-start)` after `-ss` input seeking, replacing `-to end` so trim windows with non-zero starts produce correct durations.
- Update crop args tests to assert duration-based trim behavior (`-t`) for start/end windows.
- Add in-repo Cosmos skill packaging and maintenance ritual (`skills/cosmos/*`) and enforce freshness requirements in `AGENTS.md` (POL-486).

## 0.3.3 — Encoder guardrails + HEVC preference (2026-02-11)
- Add macOS encoder guardrail in `choose_encoder_for_video`: when H.264 VideoToolbox is selected for >4K inputs, proactively fall back to `libx264` with a clear runtime tip.
- Add `--prefer-hevc-hw` for squarecrop (`squarecrop` and `cosmos crop run`) to prefer `hevc_videotoolbox` on macOS when available.
- Preserve encoder provenance clarity by keeping attempted and used encoder values through CLI/SDK/run paths.
- Expand test coverage for:
  - macOS >4K VideoToolbox guardrail behavior
  - HEVC preference selection
  - SDK pass-through of `prefer_hevc_hw`
- Docs refresh:
  - fix stale `squarecrop run` examples to current `squarecrop` command shape
  - add `docs/encoder-behavior.md` as the platform behavior matrix scaffold and link it from user/reference docs + README.

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
