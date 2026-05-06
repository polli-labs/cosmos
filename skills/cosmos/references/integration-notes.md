# Cosmos Integration Notes

## Downstream dependencies

- Cosmos is the front door for raw field media entering the Polli stack.
- Its outputs are the canonical bridge from heterogeneous source media into
  downstream Ibrida, review, and reporting flows.
- Ibrida consumes Cosmos-produced MP4 and provenance sidecars.
- Dash/polli surfaces clip/view artifacts and relies on stable join keys.
- Schema compatibility matters for cross-repo provenance stitching.
- Adapter selection (`cosm` vs `generic-media`) now impacts ingest normalization behavior and should be visible in run-level provenance for reproducibility.
- Preview bundles (`cosmos_crop_preview_run.v1.json` + per-clip `preview_plan.v1.json`) are intended as a stable contract for future local GUI review/edit flows.
- Optimize outputs (`cosmos_optimize_run.v1.json` + `*.cosmos_optimized.v1.json`) provide reproducible web-ready transform receipts for rollback-safe workflows.
- Lineage queries (`cosmos lineage ...`) are the canonical cross-run provenance traversal surface for ingest/crop/optimize outputs.
- `cosmos.sdk.video` is the shared typed video probe/frame extraction surface for downstream
  repos that need RGB frames without carrying local Decord or ad hoc FFmpeg code.
- Decord should remain an external Linux comparator/parity guardrail for downstream
  removal decisions until a maintained backend passes representative WFC benchmarks.
- PyAV is useful for explicit portability testing but should not be presented as the
  Linux performance answer. TorchCodec is explicit opt-in until shared-FFmpeg host
  posture and WFC benchmark evidence justify a stronger recommendation.

## Compatibility constraints

- Keep schema `$id` values stable for non-breaking changes.
- Bump schema versions for breaking payload changes.
- Keep `clip_id`, `view_id`, and SHA-based linkage stable.
- Keep optimize `source.sha256` / `output.sha256` fields stable and copy sidecars with MP4 outputs.
- Keep lineage index payload shape stable (`cosmos-lineage-index-v1`) so automation can persist/reuse graph snapshots.
- Keep preview plan geometry semantics aligned with execution math (rect clamp/even-round rules, square offset/center rules).
- Keep profile signaling stable in run/artifact provenance to preserve reproducibility audits.
- Keep video substrate returns as typed metadata + `rgb24` bytes; NumPy/PIL conversion belongs
  in downstream repo boundaries.
- Keep optional backend choices explicit. Do not let `auto` silently select a backend
  that is only validated by synthetic smoke tests.

## CLI evolution direction

- Preserve a unified `cosmos` command surface.
- Use `cosmos process` as the canonical ingest -> crop orchestration command; treat `cosmos pipeline` as deprecated compatibility only.
- Prefer `noun -> verb` subcommand patterns and stable machine output modes for agent users.
- Keep preview machine outputs (`--json`) stable since review tooling may automate over run/plan artifact paths.
- Keep optimize machine outputs (`--json`) stable for batch tooling and async runners.
- Keep lineage machine outputs (`--json`) stable for contract tests and provenance reconciliation jobs.

## Release-sensitive change areas

Any changes in these areas require skill freshness review:

- CLI flags/subcommands/help text
- SDK function signatures and option models
- video substrate contracts (`VideoProbe`, `RgbFrame`, extraction semantics, resolver errors)
- ffmpeg bootstrap/detection behavior
- encoder runtime-probe/fallback behavior (Linux/Windows hardware paths)
- adapter registry/auto-detection and explicit `--adapter` override semantics
- provenance schema or emitted field sets
- lineage graph/index fields and query payload shape
- determinism profile semantics and precedence (`--profile` / `COSMOS_PROFILE`)
- crop semantics (square offsets, rect coords, naming)
- preview bundle/plan schema or render contract behavior
