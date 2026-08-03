# Cosmos Skill

This page summarizes the in-repo Cosmos skill package used by agent operators.

## Why it matters

Cosmos is CLI-first and automation-heavy. The skill captures canonical workflows,
contracts, and maintenance rules so feature work stays aligned across:

- CLI surfaces (`cosmos crop ...` and related subcommands)
- SDK entry points (`cosmos.sdk.*`)
- ffmpeg/encoder behavior
- provenance fields and schema stability

## Canonical source

- Skill entrypoint: [`skills/cosmos/SKILL.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/SKILL.md)
- References directory: [`skills/cosmos/references/`](https://github.com/polli-labs/cosmos/tree/main/skills/cosmos/references)

## Required references before implementation

- API contract map:
  [`skills/cosmos/references/api-surfaces.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/api-surfaces.md)
- Architecture map:
  [`skills/cosmos/references/architecture.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/architecture.md)
- Integration notes:
  [`skills/cosmos/references/integration-notes.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/integration-notes.md)
- Maintenance ritual:
  [`skills/cosmos/references/maintenance-ritual.md`](https://github.com/polli-labs/cosmos/blob/main/skills/cosmos/references/maintenance-ritual.md)

## High-priority conventions

1. Keep business logic in `cosmos/sdk/*`; keep CLI layers thin.
2. Preserve square-crop semantics (`offset_x`/`offset_y` in `[-1, 1]`).
3. Preserve provenance join keys and schema stability.
4. Keep CLI output contracts safe for automation (`--json`, `--plain`, `--yes`, `--dry-run`).
5. Treat skill freshness as a release-quality requirement, not optional docs polish.

## Agent-native dry-runs

Use [Agent-Native Dry-Run Contract](dry-run-contract.md) as the canonical docs
target before changing dry-run behavior. Media-execution commands expose
`dry_run_plan`, typed `output_declarations`, and v1 plan artifacts with
argv-array `commands`. Dry-run does not apply the planned media transform or
create media outputs; bounded local ffmpeg/ffprobe preflight/probing may still
run when planning depends on it.

## Release checklist linkage

When CLI/SDK/provenance behavior changes, update both docs and skill references in the same lane:

- docs pages under `docs/`
- skill entrypoint and references under `skills/cosmos/`
- release notes/changelog as applicable
