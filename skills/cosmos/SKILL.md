---
name: cosmos
description: "Cosmos-dev repo knowledge -- private development mirror for the Polli video normalization toolkit. Use before modifying cosmos CLI/SDK/provenance or dev/public release workflows."
version: "0.2.10"
x:
  source_repo: "cosmos-dev"
  source_branch: "main"
  source_commit: "2825d9d"
  package_version: "0.9.0"
  generator: "codex"
  last_modified: "2026-08-03T20:31:25Z"
---

# Cosmos

Cosmos is a provenance-first video normalization toolkit. The CLI/SDK ingests heterogeneous source layouts, generates deterministic web-ready derivatives, and emits machine-joinable sidecars for reproducible downstream automation.

## Quick Facts

- Version: 0.9.0
- Canonical CLI: `cosmos` with root commands `process`, `ingest`, `crop`, `optimize`, `provenance`, `lineage`.
- Agent-native dry-run contract: `docs/dry-run-contract.md`; media-execution
  dry-runs expose `dry_run_plan`, typed `output_declarations`, and v1 plan
  artifacts with argv-array `commands`.
- Retired alias: `cosmos pipeline` is no longer a command; use `cosmos process`.
- SDK entry points: `from cosmos.sdk import ingest, IngestOptions, crop, CropJob, optimize, OptimizeOptions, probe_video, probe_video_timeline, extract_frames_at_indices, extract_frames_at_times, DeterminismProfile, resolve_profile`.
- Ingest adapter contract: `IngestAdapter` Protocol in `cosmos.ingest.adapter`; built-ins are `cosm` and `generic-media`.
- Determinism profiles: `strict|balanced|throughput` across ingest/crop/optimize.
- Profile precedence: CLI `--profile` > `COSMOS_PROFILE` env > command defaults.
- Lineage: `cosmos lineage {build,upstream,downstream,chain,tree}` and `cosmos.sdk.lineage.LineageIndex`.
- Video substrate: `cosmos.sdk.video` exposes typed `VideoProbe` metadata, immutable
  `VideoFrameTimeline` exact literal frame-PTS identities, and `RgbFrame` `rgb24`
  byte extraction without NumPy/PIL return objects; `ffmpeg-cli` is the default
  backend, optional `polli-cosmos[video-av]` enables explicit
  `COSMOS_VIDEO_BACKEND=pyav` or platform-aware `auto` experiments, and optional
  `polli-cosmos[video-torchcodec]` enables explicit
  `COSMOS_VIDEO_BACKEND=torchcodec` CPU experiments. Auto mode uses PyAV with
  FFmpeg CLI fallback on macOS and keeps FFmpeg CLI on Linux.
- Video subprocess bound: a positive finite `COSMOS_VIDEO_FFMPEG_TIMEOUT`
  applies to metadata probes, exact timeline probes, packet timestamp lookups,
  and FFmpeg RGB extraction. Unset or invalid values preserve the historical
  unbounded behavior; failures surface as typed video errors.
- Current video-decode decision posture: Decord is an external Linux comparator,
  not a Cosmos runtime dependency; PyAV is optional portability work, not the
  Linux fast path; TorchCodec is promising but explicit opt-in until
  representative WFC benchmarks pass in a managed shared-FFmpeg environment;
  PyNvVideoCodec/NVDEC is on hold until host runtime policy provides the NVIDIA
  encode libraries its wheel requires at import time.
- Provenance join key: `view.source.sha256 == clip.output.sha256`.
- Preview geometry: `PreviewRect` keeps the exact eight-field preview-plan v1 wire
  model and ffmpeg-derived pixel authority; its read-only `typus_bbox` property
  exposes a `polli-typus` 0.8 `BBoxXYWHNorm` only when the lossy normalized view
  is representable, otherwise `None` without fabricating positive extent.
- ffmpeg resolution order: `COSMOS_FFMPEG` -> `~/.local/share/cosmos/bin/ffmpeg` -> system `PATH`
- Stack role: Cosmos is the media-ingest and deterministic-derivative entry
  point for the Polli pipeline; downstream repos should consume its clips,
  views, and provenance rather than re-deriving those artifacts ad hoc

## Dev/Public Contract

- Private dev repo: `polli-labs/cosmos-dev`
- Public release repo: `polli-labs/cosmos`
- Local main clone: `~/dev/cosmos/dev`
- Local worktrees: `~/dev/cosmos/wt/<branch>`
- Public inspection clone: `~/dev/cosmos/public/cosmos`
- Canonical dev/public policy lives in the org-level `polli-dev-conventions`
  skill (`references/release-ritual.md` in `agents-infra`).
- Use `docs/migration/dev_public_release_contract.md` only for repo-local
  paths, remotes, and standing overrides.

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
6. Video-decode backend comparison or Decord-removal questions -> `docs/video-benchmark.md`

## First Steps

1. Read `AGENTS.md` in this repo.
2. Read `CONTRIBUTING.md` for contributor setup, bootstrap, and canonical quality-gate commands.
3. Use the router above and open only the minimum relevant reference file(s).
4. Capture command-surface receipts for touched surfaces with `uv run cosmos ... --help`.
5. If the task touches public release work, read the canonical
   `polli-dev-conventions` release ritual and this repo's local contract doc:
   `docs/migration/dev_public_release_contract.md`.
6. Run the canonical quality gate before handoff: `make check`.

## Working Rules

- Route contributors to `CONTRIBUTING.md` and `dev/scripts/bootstrap-dev.sh` instead of repeating setup steps in ad hoc notes.
- Keep one CLI (`cosmos`) and one SDK (`cosmos.sdk`) mental model; route business logic through SDK layers.
- Use `cosmos process` as the canonical ingest -> optional crop workflow surface.
- For public-promotion work, follow the canonical `polli-dev-conventions`
  policy and use `docs/migration/dev_public_release_contract.md` for local
  paths, remotes, and standing overrides.
- Preserve create-cli contracts: stable flag naming, explicit `--json/--plain`, and non-interactive safety flags (`--yes/--no-input`) on commands that expose prompts.
- Preserve the dry-run contract in `docs/dry-run-contract.md`: dry-run must not
  apply the planned media transform or create media outputs, validated output
  declarations only, `dry_run_plan` paths when a plan artifact is produced, and
  argv arrays rather than shell strings when executable commands are exposed.
  Bounded local ffmpeg/ffprobe preflight/probing may still run when planning
  depends on it.
- Keep explicit user overrides authoritative (for example forced encoder should fail loudly, not silently degrade).
- Preserve crop semantics (`offset_x`/`offset_y` in `[-1, 1]`; rect clamp/even-round behavior).
  `PreviewRect`'s eight serialized fields are frozen schema-v1 data; derive
  `typus_bbox` from them and treat `None` as known-but-unrepresentable geometry,
  never as permission to invent an epsilon or change a boundary.
- Keep provenance contracts and join key stable (`view.source.sha256 == clip.output.sha256`).
- Use shared ffmpeg helpers in `cosmos/ffmpeg/*` rather than shelling ad hoc `ffmpeg`/`ffprobe` commands.
- Use `probe_video_timeline()` when downstream evidence must bind a decoded frame to an
  exact stream time-base tick. Its `pts_ticks` are literal ffprobe frame `pts`; missing
  values fail closed. Do not substitute estimated timestamps or reconstruct identity from
  rounded seconds, packet-order timestamps, or nominal FPS.
- Keep optional video backends lazy-imported. Importing `cosmos.sdk.video` must not require
  PyAV/NumPy/TorchCodec/PyTorch unless the selected backend actually needs them.
- Preserve the shared video subprocess contract: resolver failures, OS-level
  launch failures (including missing or permission-denied executables), timeouts,
  and non-zero process exits become `VideoProbeError` or `VideoDecodeError`. The
  optional timeout is read from `COSMOS_VIDEO_FFMPEG_TIMEOUT` at call time.
- Do not promote optional video backends into `auto` from synthetic results alone;
  default changes need representative WFC benchmark evidence and a documented
  missing-backend failure policy.
- Use `make check` as the canonical local gate, and refresh `uv.lock` with `uv lock` whenever dependency metadata changes.

## Current Scope Snapshot

- M1 adapter architecture: `IngestAdapter` contract + `cosm`/`generic-media` adapters + auto-detect/override flow.
- M2 lineage graph surfaces: SDK index traversal + CLI query commands for upstream/downstream/chain/tree.
- M3 determinism policy: profile model (`strict|balanced|throughput`) threaded through ingest/crop/optimize and provenance.
- POL-1132/POL-1987 video substrate: typed FFmpeg-backed metadata, exact decoded-frame
  timeline probing, and frame extraction in `cosmos.video` and `cosmos.sdk.video` for
  downstream repos that should not carry ad hoc decode plumbing.
- POL-2093 preview geometry adoption: dependency-light `polli-typus` 0.8 core and an
  optional canonical `BBoxXYWHNorm` view without changing preview-plan v1 bytes.

## References

- `references/workflows.md` -- canonical agent workflows and copy/paste command recipes.
- `references/api-surfaces.md` -- CLI + SDK contract surfaces and compatibility expectations.
- `references/architecture.md` -- module map and runtime flow.
- `references/integration-notes.md` -- downstream integration and compatibility constraints.
- `references/maintenance-ritual.md` -- required skill freshness process for feature/release work.
- `references/follow-on-issue-drafts.md` -- backlog-ready issue scopes for larger follow-ons.
