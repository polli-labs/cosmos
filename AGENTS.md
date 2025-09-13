# Agent Instructions (Cosmos repo)

You may freely copy/adapt code from:

- `/Users/carbon/repo/cosm-c360-tools/**`
- `/Users/carbon/repo/pollinalysis-tools/preprocessing/squarecrop/**`

Porting rules

- Rewrite imports from `src.cosmos.*` → `cosmos.ingest.*`; remove `src/` layout assumptions.
- Keep TUI flows (questionary) but route all business logic through SDK under `cosmos/sdk`.
- Use `uv` for environment and installs.
- Prefer shared FFmpeg helpers in `cosmos/ffmpeg/*` for encoder detection and arg presets.
- All issues go to GitHub Issues (do not create a local `issues/` dir). Use labels mirroring `priority:*` and `status:*`.

Monorepo principles

- No `src/` layout; packages live at repo root under `cosmos/`.
- Two CLIs, one SDK: `cosmos` (ingest + orchestrator) and `squarecrop` (standalone crop) over a shared importable SDK.
