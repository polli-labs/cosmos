# Agent Instructions (Cosmos repo)

Purpose
- Cosmos is a small, public-bound Python library and CLI set for: (a) ingesting COSM camera outputs into standard MP4 and (b) post‑processing these MP4s into square crops — with end‑to‑end provenance artifacts for reproducibility and downstream analytics.

Repo Layout
- `cosmos/sdk/` — programmatic entry points (`ingest`, `crop`, provenance helpers). Treat this as the source of truth for business logic.
- `cosmos/ingest/` — manifest parsing, preflight, validation, processing/encoding.
- `cosmos/crop/` — square crop planning and execution; jobs file parser.
- `cosmos/ffmpeg/` — encoder detection and argument presets; shared across ingest/crop.
- `cosmos/cli/` — Typer CLIs (`cosmos`, `squarecrop`, `provenance`).
- `schema/cosmos/` and `docs/schemas/` — JSON Schemas for run‑ and artifact‑level provenance.

CLIs & SDK
- Two CLIs, one SDK.
  - `cosmos`: ingest pipeline + a convenience `pipeline` command (ingest → optional crop).
  - `squarecrop`: standalone square crop tool.
  - SDK: `from cosmos.sdk import ingest, IngestOptions, crop, CropJob`.
- Keep TUI flows (Questionary) for interactive runs; always route business logic through `cosmos/sdk` so programmatic and CLI paths stay aligned.

FFmpeg & Encoders
- Require `ffmpeg` on PATH. Cross‑platform encoder preference:
  - macOS: `h264_videotoolbox` → `libx264`
  - Linux: `h264_nvenc` → `h264_qsv` → `h264_vaapi` → `libx264`
  - Windows: `h264_nvenc` → `h264_qsv` → `h264_amf` → `libx264`
- Use shared helpers in `cosmos/ffmpeg/*` to detect encoders and build args. Filter graphs are CPU‑bound; thread flags live in the SDK options and are logged alongside commandlines.

Provenance (v1)
- Run‑level: `cosmos_ingest_run.v1.json`, `cosmos_crop_run.v1.json` (environment, encoder prefs, options/jobs).
- Artifact‑level: `*.mp4.cosmos_clip.v1.json`, `*.mp4.cosmos_view.v1.json` with output sha256, video info, encode info.
- Join keys: `view.source.sha256 == clip.output.sha256`. Keep artifacts next to outputs; copy them together.
- CLI helpers under `cosmos provenance` subcommands for hashing, listing, and reverse lookups.

Integrations (public‑safe)
- Downstream: Ibrida consumes Cosmos outputs and may embed Cosmos clip provenance by `$ref` to the published schema. Dash (in the polli monorepo) surfaces processed clips/views. Keep provenance stable; it enables reliable joins across repos.
- Types convergence: Medium‑term plan is to share artifact schemas across repos and (optionally) align OpenAPI models to `$ref` the assets‑hosted schemas. Keep schema `$id`s stable and bump versions on breaking changes.

Dev Workflow
- Env: use `uv` for virtualenv + installs. Python 3.10+.
- Quality: `make fmt` (ruff), `make lint`, `make typecheck` (mypy), `make test` (pytest).
- E2E (optional): large fixture‑gated tests live under `tests/e2e_local` and are off by default; see Makefile `e2e-repro-*` targets.

Porting Rules (when migrating older tools)
- Rewrite imports `src.cosmos.*` → `cosmos.ingest.*`; remove `src/` layout assumptions.
- Prefer shared FFmpeg helpers in `cosmos/ffmpeg/*`.
- Keep TUI but ensure all work passes through SDK.

Monorepo Principles
- No `src/` layout; packages live at repo root under `cosmos/`.
- Two CLIs, one SDK over shared modules.

Issue Tracking & Labels
- Use GitHub Issues (do not create a local `issues/` dir). Labels mirror `priority:*`, `status:*`, plus `comp:*` (ingest|crop|ffmpeg|tui|sdk).

Notes & Non‑Goals
- Avoid client‑specific references or paths in this repo. Keep documentation and examples generic and public‑ready.
- Heavy fixtures for E2E are optional and not required for CI; local devs can enable them via environment flags noted in README and tests.
