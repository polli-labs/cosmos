# Encoder Behavior by Platform

This page tracks practical encoder behavior for Cosmos CLIs/SDK across supported platforms.
Keep this as the canonical place for platform-specific limits, fallback expectations, and operator tips.

## Current policy

- macOS: `h264_videotoolbox` -> `libx264`
- Linux: `h264_nvenc` -> `h264_qsv` -> `h264_vaapi` -> `libx264`
- Windows: `h264_nvenc` -> `h264_qsv` -> `h264_amf` -> `libx264`

## macOS (validated on M1 Max)

- `h264_videotoolbox` may reject >4K inputs (for example, 7680x4320).
- Cosmos applies a guardrail: when H.264 VideoToolbox is selected and input is >4K, encoder selection skips directly to `libx264`.
- `--prefer-hevc-hw` enables an opt-in path to `hevc_videotoolbox` when available.
- Provenance captures both attempted and used encoder values so fallbacks are auditable.

Operational tips:

- For 8K jobs requiring hardware acceleration, test `--prefer-hevc-hw`.
- Keep a software fallback expectation for H.264 outputs at large resolutions.

## Linux (planned, POL-172)

Targets for deeper validation:

- NVIDIA: `h264_nvenc`
- Intel: `h264_qsv`
- VAAPI path (vendor-dependent)
- Fallback and user messaging behavior for unsupported codec/profile/pixel-format combinations

Planned additions:

- Per-encoder capability table (resolution/pix_fmt caveats)
- Probe strategy to preflight likely failures before long runs
- TUI/CLI tips for common mismatch cases

## Windows (planned, POL-173)

Targets for deeper validation:

- NVIDIA: `h264_nvenc`
- Intel: `h264_qsv`
- AMD: `h264_amf`

Planned additions mirror Linux:

- Capability matrix and caveats
- Preflight probe and fallback strategy
- User-facing guidance when hardware encode is unavailable

## Maintenance notes

- Update this page whenever encoder selection logic changes.
- Link issue IDs for each platform-specific behavior change.
- Keep examples generic and public-safe (no client-specific data paths).
