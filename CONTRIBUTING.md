# Contributing

Thanks for helping improve Cosmos.

## Development environment

Recommended setup from a local checkout:

```bash
bash dev/scripts/bootstrap-dev.sh
```

That script is designed to be idempotent and non-interactive on macOS and Linux.
It installs or validates the small set of host prerequisites Cosmos needs
(`git`, `python3`, `uv`, `ffmpeg`), then syncs a reproducible repo-local dev
environment with `uv`.

Manual setup is also fine:

```bash
make dev-setup
```

If you need docs tooling too:

```bash
make docs-setup
```

## Canonical quality gate

Cosmos now treats this as the primary local gate:

```bash
make check
```

That command runs the same quality tuple we expect before handoff:

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
- Avoid introducing unowned suppressions. Fix the source issue instead whenever
  practical.

## Optional environment variables

Cosmos does not require project-specific secrets for local development.

- `COSMOS_FFMPEG=/path/to/ffmpeg` lets you override FFmpeg discovery if you need
  a non-default binary.

## Notes to avoid surprises

- Windows `CREATE_NO_WINDOW` shim
  - Some unit tests patch `os.name = "nt"` to exercise Windows‑specific code paths on non‑Windows runners. To keep those tests working cross‑platform, we install a lightweight shim in `cosmos/ingest/processor.py` that defines `subprocess.CREATE_NO_WINDOW = 0` when the attribute is missing.
  - Guidance: it’s fine to pass `creationflags=subprocess.CREATE_NO_WINDOW` to `subprocess.run`. On non‑Windows, this resolves to `0`. Avoid hard‑coding magic numbers.

- Encoder detection during dry‑run
  - For `squarecrop`, when `dry_run=True` we skip hardware encoder detection and default to `libx264`. This keeps tests deterministic and avoids platform quirks or mocked `subprocess.run` issues.
  - Guidance: in tests that assert on constructed ffmpeg args, don’t expect platform‑specific encoders when `dry_run=True`. If you need to validate detection, run without `dry_run` and ensure ffmpeg is available on the runner.

If you run into CI failures related to these, ping the maintainers or open an issue with the failing job link so we can tune the harness.
