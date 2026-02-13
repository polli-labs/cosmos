# Cosmos Follow-on Issue Drafts (2026-02-13)

Draft issues and PR scopes derived from current repo state, create-cli guidance, and RLM scoping.

## 1) CLI redesign follow-on (post POL-472)

### Proposed Linear issue

- Title: `POL-485: CLI redesign for progressive-disclosure + machine-safe contracts (create-cli aligned)`
- Suggested labels:
  - `scope:cosmos`
  - `comp:cli`
  - `type:enhancement`
  - `priority:p1`
  - `skill:cosmos`

### Decision

Keep a unified `cosmos` CLI as the canonical interface, preserve `squarecrop` as compatibility alias for one minor cycle, and standardize machine-safe output contracts.

### Scope

- Normalize command grammar around noun-verb consistency while keeping current capabilities.
- Introduce strict output contracts:
  - user-facing progress/logs on `stderr`
  - machine payloads on `stdout`
  - stable `--json` and `--plain` modes.
- Add explicit non-interactive semantics:
  - `--yes` / `--no-input`
  - no prompt behavior in non-TTY contexts.
- Define and implement exit-code map.

### Out of scope

- Encoder policy changes.
- Provenance schema version bumps.
- Full package/module split.

### Acceptance criteria

- `cosmos <subcommand> --json` emits parseable JSON to stdout with no mixed log lines.
- Missing required inputs in non-interactive mode fail with actionable error and non-zero exit.
- `squarecrop` remains functional but prints deprecation warning and target removal version.
- CLI docs updated to reflect canonical surface and migration path.

### Recommended PR split

1. PR A: output/error contract and exit-code map (`--json`/`--plain`, stderr discipline, tests).
2. PR B: command-tree normalization + deprecation shims (`squarecrop`, `pipeline` behavior notices).
3. PR C: docs/migration guide + command examples + regression tests for non-interactive flows.

## 2) Standing recurring issue for skill freshness ritual

### Proposed Linear issue

- Title: `POL-486: COSMOS: Skill freshness audit (recurring) + in-repo skill governance bootstrap`
- Suggested labels:
  - `scope:cosmos`
  - `skill:cosmos`
  - `type:maintenance`
  - `area:agents`
  - `cadence:release`

### Issue body

```md
Purpose
- Keep `skills/cosmos/` aligned with shipped Cosmos behavior and release state.

Cadence
- Required at version bump/release tag prep and after major feature merges that change CLI/SDK/provenance behavior.

Checklist
- [ ] `skills/cosmos/SKILL.md` updated (`source_commit`, `package_version`, behavior notes)
- [ ] references updated (`api-surfaces`, `architecture`, `integration-notes`)
- [ ] CLI receipts captured (`cosmos --help`, `cosmos ingest run --help`, `cosmos crop run --help`)
- [ ] quality gate receipts captured (`make fmt && make lint && make typecheck && make test`)
- [ ] drift risks / follow-ons logged

Receipts
- Commit(s):
- Commands run:
- Files changed:
- Drift notes:
```

### Enforcement hooks

- Required rule is recorded in `AGENTS.md`.
- Release prep should block tag cut until checklist receipts are posted.
- PRs changing CLI/SDK/provenance should include "skill updated" notes.

## 3) Phase 5 automated 8K E2E follow-on

### Proposed Linear issue

- Title: `POL-487: Phase 5: Automated 8K E2E with fixture-gated CI + local real-media lanes`
- Suggested labels:
  - `scope:cosmos`
  - `comp:test`
  - `type:enhancement`
  - `priority:p1`

### Decision

Adopt tiered validation: synthetic 8K checks in CI, real 8K media checks in `e2e_local`/nightly/manual lanes.

### Scope

- Add synthetic 8K ffmpeg fixture path suitable for CI runtime limits.
- Add fixture-gated real-media tests in `tests/e2e_local`.
- Encode CI/non-CI boundary explicitly in test markers and docs.
- Emit reproducibility receipts (`cmd.txt`, `log.txt`, provenance sidecars) in E2E outputs.

### Data assumptions

- Synthetic fixtures are generated on-demand from ffmpeg filters (no large binary in repo).
- Real 8K source clips live outside repo and are opt-in via env vars.

### CI vs non-CI boundary

- CI required:
  - parser/coord math correctness for rect jobs
  - synthetic 8K dry-run and minimal execution path
  - provenance field assertions
- Non-CI required:
  - real 8K encode behavior, hardware fallback behavior, throughput smoke checks

### Acceptance criteria

- CI lane validates synthetic 8K crop/provenance path in bounded runtime.
- Local/nightly lane validates at least one real 8K clip with receipt artifacts.
- Tests are skipped with clear reason when fixtures or env gates are absent.
- Failures include triage hints (fixture missing vs ffmpeg/bootstrap vs encoder failure).

### Recommended PR split

1. PR A: synthetic fixture + CI-safe tests + markers.
2. PR B: `e2e_local` real-clip scenarios + gating/docs.
3. PR C: nightly/manual runner wiring and triage runbook.
