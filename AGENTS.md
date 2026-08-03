---
title: "Cosmos — Agent/Dev Guide"
doc_type: "agents"
status: "active"
owner: "polli-labs"
last_modified: "2026-08-03T20:25:07Z"
last_reviewed: "2026-08-03T20:25:07Z"
scope: "repository:cosmos"
---

# Cosmos — Agent/Dev Guide

Repo-specific instructions for `polli-labs/cosmos`.
Keep this file public-safe: no private customer or project context belongs here.

## Canonical model

- Current package version: `0.9.0`
- One CLI: `cosmos`
- One SDK: `cosmos.sdk`
- One instruction source: `AGENTS.md`, with `CLAUDE.md` as a symlink to
  `AGENTS.md` when possible.

Cosmos is a provenance-first video normalization toolkit:

- ingest heterogeneous video layouts through adapters;
- generate deterministic web-ready derivatives;
- emit machine-joinable provenance sidecars;
- expose typed video metadata, exact decoded-frame identities, and RGB frames.

## Command and SDK surfaces

- Root commands:
  - `cosmos process`
  - `cosmos ingest`
  - `cosmos crop`
  - `cosmos optimize`
  - `cosmos provenance`
  - `cosmos lineage`
- `cosmos process` is the canonical ingest-to-optional-crop flow.
- The legacy `cosmos pipeline` alias is retired and must not appear in new
  documentation or automation.
- `cosmos.sdk.video` exposes:
  - `VideoProbe`
  - `VideoFrameTimeline`
  - `RgbFrame`
  - `probe_video()`
  - `probe_video_timeline()`
  - `extract_frames_at_indices()`
  - `extract_frames_at_times()`
- Importing `cosmos.sdk.video` must not require PyAV, NumPy, TorchCodec, or
  PyTorch unless an optional backend that needs them is selected.

## Dry-run contract

The canonical contract is `docs/dry-run-contract.md`.

- Media-execution dry-runs must not apply the planned transform or create media
  outputs.
- Inputs and options still validate before declared outputs are reported.
- CLI JSON includes `dry_run_plan` when a plan artifact is produced.
- Executable plan entries are argv arrays, never shell command strings.
- Dry-run planning may write declared plan metadata, but it must not fabricate
  placeholder MP4 files or per-output artifact sidecars.
- Bounded local ffmpeg or ffprobe preflight may still run when planning depends
  on source metadata or executable resolution.

## Exact video timeline contract

Use `probe_video_timeline()` when evidence must bind to exact decoded frames.

- `VideoFrameTimeline` contains the first video stream's integer time base and
  one literal ffprobe frame `pts` tick per decoded frame, in emitted frame
  order.
- Missing, non-integral, duplicate, or nonmonotonic PTS identities fail closed.
- Do not substitute rounded seconds, nominal-FPS arithmetic, packet-order
  timestamps, best-effort timestamps, or estimated identities.
- A positive finite `COSMOS_VIDEO_FFMPEG_TIMEOUT` bounds metadata probes,
  timeline probes, packet timestamp lookups, and FFmpeg RGB extraction.
- Unset, blank, invalid, non-positive, or non-finite timeout values preserve
  historical unbounded behavior.
- Resolver, launch, timeout, and process failures remain typed
  `VideoProbeError` or `VideoDecodeError`.

## Preview geometry contract

`PreviewRect` preserves the preview-plan v1 wire contract.

- Its serialized source of truth remains exactly:
  - `x_px`
  - `y_px`
  - `w_px`
  - `h_px`
  - `x_norm`
  - `y_norm`
  - `w_norm`
  - `h_norm`
- Pixel coordinates remain the authoritative ffmpeg-derived geometry after
  truncation, even rounding, and frame-bound clamping.
- `PreviewRect.typus_bbox` is a read-only derived
  `polli-typus` `BBoxXYWHNorm | None`.
- `typus_bbox` is not serialized as a ninth field.
- `None` means the known lossy normalized rectangle is not representable by
  Typus. It does not mean geometry is missing and is never permission to
  fabricate an epsilon or adjust a boundary.

## Repository map

- `cosmos/sdk/` — public business-logic entry points
- `cosmos/ingest/` — adapter contract, discovery, and ingest behavior
- `cosmos/crop/` — square and rectangle crop execution
- `cosmos/preview/` — preview contracts, geometry planning, and rendering
- `cosmos/video/` — typed probe, exact timeline, and frame extraction
- `cosmos/ffmpeg/` — executable resolution and shared command helpers
- `cosmos/cli/` — thin Typer wrappers over SDK surfaces
- `schema/cosmos/`, `docs/schemas/` — provenance schema contracts
- `skills/cosmos/` — release-critical in-repo Cosmos skill package

## Adapter and determinism model

- Ingest adapter contract: `IngestAdapter` in `cosmos.ingest.adapter`
- Built-in adapters:
  - `cosm`
  - `generic-media`
- Determinism profiles:
  - `strict`
  - `balanced`
  - `throughput`
- Profile precedence:
  - CLI `--profile`
  - `COSMOS_PROFILE`
  - command default

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

- Keep CLI wrappers thin and route behavior through `cosmos/sdk/*`.
- Preserve machine-safe output patterns, including `--json`, `--plain`, and
  stable field names.
- Keep explicit user overrides authoritative. A forced encoder must fail
  clearly rather than silently selecting another implementation.
- Preserve square-offset and rectangle clamp/even-round behavior.
- Use shared ffmpeg helpers rather than constructing ad hoc subprocess
  commands.
- Keep optional video backends lazy-imported.
- Preserve public errors and the shared video timeout contract.
- Use `make check` as the canonical local gate.
- Refresh `uv.lock` with `uv lock` whenever dependency metadata changes.

## Release ritual

Before a public release tag:

1. Update affected docs and examples, then run
   `uv run mkdocs build --strict`.
2. Update `skills/cosmos/SKILL.md` and relevant skill references.
3. Refresh this file and
   `docs/migration/dev_public_release_contract.md` when the public/private
   boundary changes.
4. Run:
   - `uv lock --check`
   - `make check`
   - locked release-environment sync
   - wheel build
   - `twine check`
   - isolated installation from the built wheel
   - installed-wheel import smoke for video, timeline, and PreviewRect Typus
     geometry
5. Tag and publish from `polli-labs/cosmos` only.
6. Record the PR, exact candidate SHA, tag, workflow run, release asset, PyPI
   artifact, and matching hashes in the owning Linear issue.

Treat docs, skill, instructions, wheel installation, and release receipts as
release-quality requirements.

## Canonical commands

```bash
make check
uv lock --check
uv run mkdocs build --strict
uv run cosmos --help
uv run cosmos process --help
uv run cosmos ingest run --help
uv run cosmos crop run --help
uv run cosmos optimize run --help
uv run cosmos lineage --help
```

## Public/private boundary

The reviewed private repository is `polli-labs/cosmos-dev`; this repository is
the public release surface.

Public promotion defaults to the complete immutable reviewed private tree, with
exactly four public-owned exceptions:

1. `AGENTS.md`
2. `.github/workflows/codeql.yml`
3. `.github/workflows/docs.yml`
4. `.github/workflows/publish.yml`

The public docs workflow is build-only until a deployment owner is established.
The public publish workflow is the sole tag-triggered package and GitHub-release
mutation authority. Public CodeQL remains owned by the repository's public
security configuration.

Any fifth divergent path is unclassified drift and must fail promotion closed.
