# Contributing

Thanks for helping improve Cosmos.

## Development environment

Recommended setup from a local checkout:

```bash
bash dev/scripts/bootstrap-dev.sh
```

That script is idempotent and non-interactive on macOS and Linux. It installs
or validates the small host prerequisite set Cosmos needs (`git`, `python3`,
`uv`, `ffmpeg`), then syncs the repo-local environment from the committed
`uv.lock`.

Manual setup is also fine:

```bash
make dev-setup
```

If you need docs tooling too:

```bash
make docs-setup
```

If you change `pyproject.toml` or any dependency inputs, refresh the lockfile:

```bash
uv lock
```

## Canonical quality gate

Run this before handing off a change:

```bash
make check
```

That command runs the same core tuple we expect in CI:

- `ruff format --check`
- `ruff check`
- `ty check`
- `pytest -q`

Individual targets remain available when you only need one surface:

```bash
make fmt
make lint
make typecheck
make test
```

## Type-check policy

- `ty` is the required type gate for Cosmos.
- Warnings are fatal.
- The typed surface includes both `cosmos/**/*.py` and `tests/**/*.py`.
- Avoid introducing unowned suppressions. Fix the source issue instead whenever practical.

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

## Optional environment variables

Cosmos does not require project-specific secrets for local development.

- `COSMOS_FFMPEG=/path/to/ffmpeg` lets you override FFmpeg discovery if you need a
  non-default binary.

## Documentation and skill freshness

When CLI/SDK/provenance behavior changes, update docs and skill references in the same PR:

- docs under `docs/`
- skill package under `skills/cosmos/`
- release notes in `CHANGELOG.md` when applicable

## Reporting issues

- Use GitHub Issues for bugs, feature requests, and tech debt.
- For security vulnerabilities, do not open public issues. Follow `SECURITY.md`.
