# Contributing

Thanks for helping improve Cosmos.

## Development setup

```bash
uv venv .venv
. .venv/bin/activate
uv pip install -e ".[dev]"
```

## Quality gate (required before PR)

```bash
make fmt
make lint
make typecheck
make test
```

## Architecture expectations

- Keep business logic in SDK/runtime modules (`cosmos/sdk/*`, `cosmos/*`) and keep CLI glue thin.
- Prefer shared ffmpeg helpers in `cosmos/ffmpeg/*` over ad-hoc command construction.
- Preserve provenance contracts and join semantics across ingest/crop/optimize outputs.

## Test and CI notes

- Windows `CREATE_NO_WINDOW` shim:
  - Some tests patch `os.name = "nt"` on non-Windows hosts.
  - `cosmos/ingest/processor.py` defines `subprocess.CREATE_NO_WINDOW = 0` when missing.
  - Use `creationflags=subprocess.CREATE_NO_WINDOW` rather than hard-coded values.

- Encoder detection during `--dry-run`:
  - For `cosmos crop run`, when `dry_run=True`, hardware encoder probing is skipped and the
    plan defaults to `libx264` for deterministic tests.
  - Tests asserting ffmpeg args in dry-run mode should not expect host-specific hardware encoders.
  - To validate runtime probing behavior, run without dry-run on a host with ffmpeg available.

## Documentation and skill freshness

When CLI/SDK/provenance behavior changes, update docs and skill references in the same PR:

- docs under `docs/`
- skill package under `skills/cosmos/`
- release notes in `CHANGELOG.md` when applicable

## Reporting issues

- Use GitHub Issues for bugs, feature requests, and tech debt.
- For security vulnerabilities, do not open public issues. Follow `SECURITY.md`.
