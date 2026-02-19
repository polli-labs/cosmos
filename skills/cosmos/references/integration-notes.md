# Cosmos Integration Notes

## Downstream dependencies

- Ibrida consumes Cosmos-produced MP4 and provenance sidecars.
- Dash/polli surfaces clip/view artifacts and relies on stable join keys.
- Schema compatibility matters for cross-repo provenance stitching.
- Preview bundles (`cosmos_crop_preview_run.v1.json` + per-clip `preview_plan.v1.json`) are intended as a stable contract for future local GUI review/edit flows.

## Compatibility constraints

- Keep schema `$id` values stable for non-breaking changes.
- Bump schema versions for breaking payload changes.
- Keep `clip_id`, `view_id`, and SHA-based linkage stable.
- Keep preview plan geometry semantics aligned with execution math (rect clamp/even-round rules, square offset/center rules).

## CLI evolution direction

- Preserve a unified `cosmos` command surface.
- Treat `squarecrop` as compatibility surface while planning eventual deprecation.
- Prefer `noun -> verb` subcommand patterns and stable machine output modes for agent users.
- Keep preview machine outputs (`--json`) stable since review tooling may automate over run/plan artifact paths.

## Release-sensitive change areas

Any changes in these areas require skill freshness review:

- CLI flags/subcommands/help text
- SDK function signatures and option models
- ffmpeg bootstrap/detection behavior
- provenance schema or emitted field sets
- crop semantics (square offsets, rect coords, naming)
- preview bundle/plan schema or render contract behavior
