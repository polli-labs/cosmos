# Cosmos Skill Freshness Ritual (Required)

This ritual is required whenever Cosmos feature work lands or a release/version bump is prepared.

## Trigger conditions

Run this ritual when any of the following happens:

- A PR merged to `main` changes `cosmos/cli/*`, `cosmos/sdk/*`, `cosmos/crop/*`, `cosmos/ffmpeg/*`, `schema/cosmos/*`, or provenance docs.
- `pyproject.toml` version changes.
- A new release tag is prepared.

## Mandatory checklist

1. Update `skills/cosmos/SKILL.md` quick facts:
   - `source_commit`
   - `package_version`
   - behavior summary if changed.
2. Update reference docs touched by behavior drift:
   - `skills/cosmos/references/api-surfaces.md`
   - `skills/cosmos/references/architecture.md`
   - `skills/cosmos/references/integration-notes.md`
3. Validate command surface receipts:
   - `. .venv/bin/activate && cosmos --help`
   - `. .venv/bin/activate && cosmos ingest run --help`
   - `. .venv/bin/activate && cosmos crop run --help`
   - `. .venv/bin/activate && cosmos optimize run --help`
4. Run quality gate:
   - `make fmt && make lint && make typecheck && make test`
5. Post receipts to the standing Linear issue (template below).

## Standing Linear issue scaffold

Suggested title:
- `COSMOS: Skill Freshness Audit (Recurring)`

Suggested labels:
- `scope:cosmos`
- `skill:cosmos`
- `type:maintenance`
- `area:agents`
- `cadence:release`

Suggested body:

```md
Purpose
- Keep `skills/cosmos/` aligned with shipped CLI/SDK/provenance behavior.

Cadence
- Run at each version bump/release-tag prep and after major feature merges.

Required checklist
- [ ] SKILL.md updated (`source_commit`, `package_version`, changed behavior notes)
- [ ] references updated for changed surfaces
- [ ] CLI help receipts captured
- [ ] `make fmt && make lint && make typecheck && make test` receipts captured
- [ ] drift risks and follow-ups documented

Receipts
- Commit(s):
- Commands run:
- Files changed:
- Drift notes:
```

## Enforcement points

- `AGENTS.md` includes this ritual as a required repo rule.
- PRs that change CLI/SDK/provenance behavior should include explicit "skill updated" receipt in PR notes.
- Release prep should block final cut until this checklist is complete.
