# Encoder Behavior by Platform

This page documents Cosmos encoder selection, ffmpeg resolution order, determinism profiles, and known platform caveats.

## Determinism profiles

Cosmos supports named determinism profiles that control encoder selection, thread pinning, and bitexact flags:

| Profile      | Encoder policy   | Threads | Scale filter | Bitexact | Use case                        |
|-------------|-----------------|---------|-------------|----------|--------------------------------|
| `strict`    | `libx264` only  | 4       | lanczos     | yes      | CI, cross-host comparison       |
| `balanced`  | auto-fallback   | auto    | default     | no       | Default (same as no profile)    |
| `throughput`| prefer-hardware | auto    | bicubic     | no       | Bulk processing                 |

Set via CLI `--profile strict`, SDK `profile="strict"`, or env `COSMOS_PROFILE=strict`.

Resolution precedence: explicit `--profile` > `COSMOS_PROFILE` env > `None` (legacy).
Per-field CLI overrides (e.g. `--encoder`, `--crf`) always win over profile defaults.

## Current encoder preference policy

- macOS: `h264_videotoolbox` -> `libx264`
- Linux: `h264_nvenc` -> `h264_qsv` -> `h264_vaapi` -> `libx264`
- Windows: `h264_nvenc` -> `h264_qsv` -> `h264_amf` -> `libx264`

## Runtime fallback behavior

When Cosmos auto-selects hardware encoders (for example in `cosmos optimize run --mode auto`),
it now performs a runtime viability probe against the selected input and expected output settings.

If the probe fails, Cosmos falls back to `libx264` and records the attempted hardware path in provenance.

If an operator explicitly forces `--encoder`, Cosmos treats that choice as authoritative and surfaces
ffmpeg failure directly.

## ffmpeg binary resolution order

Cosmos resolves ffmpeg in this order:

1. `COSMOS_FFMPEG` environment variable (explicit override)
2. `~/.local/share/cosmos/bin/ffmpeg` (Cosmos-managed install)
3. system PATH (`ffmpeg`)

The same order applies to ffprobe via `COSMOS_FFPROBE`.

## Linux + NVIDIA bootstrap (POL-464)

### Problem

Stock Ubuntu/Debian ffmpeg packages often lack NVENC support, causing software fallback.

### Cosmos behavior

On Linux runs, Cosmos checks:

1. whether NVIDIA appears present (`nvidia-smi` or `/proc/driver/nvidia/version`)
2. whether the resolved ffmpeg binary supports `h264_nvenc`

If GPUs are present but NVENC is missing, Cosmos can offer a scoped ffmpeg bootstrap
into `~/.local/share/cosmos/bin/`.

### Suppressing checks/prompts

- `--skip-ffmpeg-check` skips bootstrap checks
- `--yes` prevents interactive prompting
- `COSMOS_FFMPEG=/path/to/ffmpeg` forces a known binary

## macOS notes

- `h264_videotoolbox` may reject very large inputs (for example 8K).
- Use `--prefer-hevc-hw` to try `hevc_videotoolbox` first where appropriate.
- Provenance captures attempted/used encoder values for auditability.

## Windows notes

Windows support follows the same fallback model, but wider hardware matrix validation is tracked
as follow-on work (see POL-173).

## Maintenance guidance

Update this page whenever encoder policy, probe behavior, or fallback semantics change.
