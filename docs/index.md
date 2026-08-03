# Cosmos Documentation

Cosmos is a provenance-first video normalization toolkit for producing
traceable MP4 derivatives.

It is designed to be safe for both humans and automation:

- one CLI (`cosmos`)
- one SDK (`cosmos.sdk.*`)
- run-level and artifact-level provenance for real outputs

## What Cosmos is (and is not)

Cosmos is currently strongest in three areas:

- COSM-native ingest: manifest-aware conversion from camera exports to MP4 clips.
- General MP4 post-processing: crop, preview, optimize, provenance, and lineage operations for standard MP4 inputs.
- Typed video substrate access: ffprobe-backed metadata, exact decoded-frame PTS timelines, and
  RGB frame extraction for SDK consumers.

Cosmos is not limited to a single camera vendor at the architecture level. The long-term model is:

- many ingest adapters
- one normalized MP4 contract
- one typed video probe/timeline/decode substrate
- one provenance model

## Start with the workflow you need

### Ingest raw camera output into MP4 clips

- Read: [Ingest User Guide](ingest-user-guide.md)
- Validate source layout: [Input Structure](input-structure.md)
- Command reference: [cosmos CLI](cosmos-cli.md)

### Create square/rect views and visual QA previews

- Read: [Crop User Guide](crop-user-guide.md)
- Commands: [cosmos CLI](cosmos-cli.md)
- Preview output contracts: [Provenance](provenance.md)

### Optimize existing MP4s for web delivery

Use `cosmos optimize run` when you need `faststart` relocation,
optional transcode transforms, and reproducible optimize provenance.

- Command details: [cosmos CLI](cosmos-cli.md)
- Encoder fallback policy: [Encoder Behavior](encoder-behavior.md)

## Command quickstart

```bash
cosmos --help
cosmos process --help
cosmos ingest run --help
cosmos crop run --help
cosmos optimize run --help
cosmos crop preview --help
cosmos provenance --help
```

## Provenance is a first-class contract

Cosmos writes run-level and artifact-level JSON sidecars for real outputs. If a
required artifact sidecar cannot be written, the real run fails instead of
silently producing an unreceipted output.

- Overview and join keys: [Provenance](provenance.md)
- Schemas: see the [Reference](#reference-map) section below

## Agent-friendly usage (Cosmos skill)

The canonical Cosmos skill package is versioned in-repo and should be used when planning
or shipping CLI/SDK/provenance changes.

- Skill entrypoint: [`skills/cosmos/SKILL.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/SKILL.md)
- API surface reference: [`skills/cosmos/references/api-surfaces.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/api-surfaces.md)
- Maintenance ritual: [`skills/cosmos/references/maintenance-ritual.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/maintenance-ritual.md)

For a docs-local summary, see [Cosmos Skill](agent-skill.md).

## Reference map

- CLI reference: [cosmos CLI](cosmos-cli.md)
- SDK API entry points: [SDK](sdk.md)
- Platform encoder behavior: [Encoder Behavior](encoder-behavior.md)
- Schemas:
  - [ingest_run.v1.json](schemas/ingest_run.v1.json)
  - [clip.v1.json](schemas/clip.v1.json)
  - [crop_run.v1.json](schemas/crop_run.v1.json)
  - [view.v1.json](schemas/view.v1.json)
  - [optimize_run.v1.json](schemas/optimize_run.v1.json)
  - [optimized.v1.json](schemas/optimized.v1.json)
  - [crop_preview_run.v1.json](schemas/crop_preview_run.v1.json)
  - [crop_preview_plan.v1.json](schemas/crop_preview_plan.v1.json)
