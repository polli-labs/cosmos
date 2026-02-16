# Cosmos Integration Notes

## Downstream dependencies

- Ibrida consumes Cosmos-produced MP4 and provenance sidecars.
- Dash/polli surfaces clip/view artifacts and relies on stable join keys.
- Schema compatibility matters for cross-repo provenance stitching.

## Compatibility constraints

- Keep schema `$id` values stable for non-breaking changes.
- Bump schema versions for breaking payload changes.
- Keep `clip_id`, `view_id`, and SHA-based linkage stable.

## CLI evolution direction

- Preserve a unified `cosmos` command surface.
- Treat `squarecrop` as compatibility surface while planning eventual deprecation.
- Prefer `noun -> verb` subcommand patterns and stable machine output modes for agent users.

## Release-sensitive change areas

Any changes in these areas require skill freshness review:

- CLI flags/subcommands/help text
- SDK function signatures and option models
- ffmpeg bootstrap/detection behavior
- provenance schema or emitted field sets
- crop semantics (square offsets, trim windows, naming)
