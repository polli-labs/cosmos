# Cosmos Documentation

Cosmos is a provenance-first video normalization toolkit.

It is designed to be safe for both humans and automation:

- one CLI (`cosmos`)
- one SDK (`cosmos.sdk.*`)
- deterministic provenance artifacts for every real output

## What Cosmos is (and is not)

Cosmos is currently strongest in two areas:

- COSM-native ingest: manifest-aware conversion from camera export layouts to normalized MP4 clips.
- General MP4 post-processing: crop, preview, optimize, and provenance operations that work on standard MP4 inputs.

Cosmos is not limited to a single camera vendor at the architecture level. The long-term model is:

- many ingest adapters
- one normalized runtime contract
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
cosmos ingest run --help
cosmos crop run --help
cosmos optimize run --help
cosmos crop preview --help
cosmos provenance --help
```

## Provenance is a first-class contract

Cosmos writes run-level and artifact-level JSON sidecars so downstream systems can audit
exactly how each file was produced.

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
