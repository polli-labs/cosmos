# Contributing

Thanks for helping improve Cosmos. A couple of test/CI notes to avoid surprises:

- Windows `CREATE_NO_WINDOW` shim
  - Some unit tests patch `os.name = "nt"` to exercise Windows‑specific code paths on non‑Windows runners. To keep those tests working cross‑platform, we install a lightweight shim in `cosmos/ingest/processor.py` that defines `subprocess.CREATE_NO_WINDOW = 0` when the attribute is missing.
  - Guidance: it’s fine to pass `creationflags=subprocess.CREATE_NO_WINDOW` to `subprocess.run`. On non‑Windows, this resolves to `0`. Avoid hard‑coding magic numbers.

- Encoder detection during dry‑run
  - For `squarecrop`, when `dry_run=True` we skip hardware encoder detection and default to `libx264`. This keeps tests deterministic and avoids platform quirks or mocked `subprocess.run` issues.
  - Guidance: in tests that assert on constructed ffmpeg args, don’t expect platform‑specific encoders when `dry_run=True`. If you need to validate detection, run without `dry_run` and ensure ffmpeg is available on the runner.

If you run into CI failures related to these, ping the maintainers or open an issue with the failing job link so we can tune the harness.
