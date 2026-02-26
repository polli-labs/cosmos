# Changelog

All notable changes to this project will be documented in this file.

## 0.5.0 — Optimize command + provenance + cross-platform encoder hardening (2026-02-26)
- Add `cosmos optimize run` CLI and SDK support (`OptimizeOptions`, `optimize`) for web-ready MP4 transforms with `auto|remux|transcode` modes.
- Add optimize provenance contracts:
  - run-level `cosmos_optimize_run.v1.json`
  - artifact-level `*.mp4.cosmos_optimized.v1.json`
  - published schemas under both `schema/cosmos/` and `docs/schemas/`.
- Add optimize command/API/docs/skill references and contract tests for JSON output, validation, and failure mapping.
- Harden encoder behavior for Linux/Windows/macOS:
  - runtime-probe auto-selected hardware encoders on real inputs and fall back to `libx264` when unavailable (for example, advertised NVENC without working driver/runtime).
  - preserve strict behavior for explicitly forced encoders (`--encoder`), surfacing ffmpeg failures instead of silently switching implementations.

## 0.4.1 — Fix rect crop trim duration (2026-02-20)
- Fix: `_build_rect_crop_args` used `-to {end}` instead of `-t {duration}`, producing wrong output
  duration when `start > 0`. With `-ss` before `-i`, ffmpeg resets the timestamp origin; `-to` was
  treated as output-relative position, yielding clips longer than the requested trim window.
  Aligns rect path with the already-correct square crop arg builder.

## 0.4.0 — Crop preview contact sheets + stacked overlays (2026-02-17)
- Add non-interactive crop preview pipeline with layered architecture under `cosmos/preview/`:
  - planner (geometry + selector resolution),
  - frame extraction (ffmpeg),
  - static renderer (contact sheets + stacked overlays).
- Add SDK preview entry points:
  - `preview(input_videos, jobs, out_dir, *, options)`
  - `preview_curated_views(pairs, out_dir, *, options)`
- Add new crop CLI surfaces:
  - `cosmos crop preview`
  - `cosmos crop curated-views-preview`
- Add new versioned preview contracts and schemas:
  - `cosmos_crop_preview_run.v1.json`
  - per-clip `preview_plan.v1.json`
  - schema files under both `docs/schemas/` and `schema/cosmos/`.
- Add tests for selector parsing, geometry planning warnings, and CLI JSON contracts.
- Update docs + Cosmos skill references with preview workflow and artifact layout.

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
