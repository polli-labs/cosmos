# Encoder Behavior by Platform

This page tracks practical encoder behavior for Cosmos CLIs/SDK across supported platforms.
Keep this as the canonical place for platform-specific limits, fallback expectations, and operator tips.

## Current policy

- macOS: `h264_videotoolbox` -> `libx264`
- Linux: `h264_nvenc` -> `h264_qsv` -> `h264_vaapi` -> `libx264`
- Windows: `h264_nvenc` -> `h264_qsv` -> `h264_amf` -> `libx264`

## ffmpeg binary resolution order

Cosmos resolves the ffmpeg binary in this order:

1. `COSMOS_FFMPEG` environment variable (explicit override)
2. `~/.local/share/cosmos/bin/ffmpeg` (cosmos-managed install via bootstrap)
3. System PATH (`shutil.which("ffmpeg")`)

Same order applies to ffprobe via `COSMOS_FFPROBE`.

## Linux + NVIDIA bootstrap (POL-464)

### Problem

Stock Ubuntu/Debian ffmpeg packages do not include NVENC support. On a machine with NVIDIA GPUs, cosmos silently falls back to `libx264` (software encoding), which is significantly slower.

### Automatic detection and bootstrap

When running `cosmos crop run` or `cosmos ingest run` on Linux, cosmos checks:

1. Is an NVIDIA GPU present? (via `nvidia-smi` on PATH or `/proc/driver/nvidia/version`)
2. Does the resolved ffmpeg support `h264_nvenc`?

If GPUs are present but NVENC is missing, cosmos offers to download a static ffmpeg build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) (~135 MB). These builds include `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`, CUVID decoders, and `cuda` hwaccel. They target glibc 2.28+ (Ubuntu 20.04+).

The downloaded binaries are installed to `~/.local/share/cosmos/bin/` (cosmos-scoped, does not pollute system PATH). On subsequent runs, cosmos finds and uses them automatically via the resolution order above.

### Suppressing the prompt

- `--skip-ffmpeg-check` on any CLI command skips the bootstrap check entirely.
- In non-interactive mode (`--yes`), the bootstrap still warns but does not prompt for download.
- Set `COSMOS_FFMPEG=/path/to/ffmpeg` to bypass all automatic resolution.

## macOS (validated on M1 Max)

- `h264_videotoolbox` may reject >4K inputs (for example, 7680x4320).
- Cosmos applies a guardrail: when H.264 VideoToolbox is selected and input is >4K, encoder selection skips directly to `libx264`.
- `--prefer-hevc-hw` enables an opt-in path to `hevc_videotoolbox` when available.
- Provenance captures both attempted and used encoder values so fallbacks are auditable.
- No bootstrap needed: `brew install ffmpeg` includes VideoToolbox support out of the box.

Operational tips:

- For 8K jobs requiring hardware acceleration, test `--prefer-hevc-hw`.
- Keep a software fallback expectation for H.264 outputs at large resolutions.

## Linux (POL-172)

Targets for deeper validation:

- NVIDIA: `h264_nvenc` (auto-bootstrapped via POL-464)
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

Windows NVENC bootstrap is out of scope for now (POL-464 covers Linux only).

## Maintenance notes

- Update this page whenever encoder selection logic changes.
- Link issue IDs for each platform-specific behavior change.
- Keep examples generic and public-safe (no client-specific data paths).
