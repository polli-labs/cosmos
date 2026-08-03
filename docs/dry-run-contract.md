# Agent-Native Dry-Run Contract

Cosmos dry-runs are safe previews for humans, scripts, and agents. They must
not apply the planned media transform, create media outputs, or perform remote
mutation, but the command still validates inputs and writes bounded metadata
artifacts so the plan can be inspected, diffed, or replayed by another tool.

This page is the canonical v1 dry-run contract for media-execution commands.

## Vocabulary

- `dry_run`: no planned media transform is applied, no media outputs are
  created, and no remote mutation occurs. Commands may still run bounded local
  ffmpeg/ffprobe preflight, probing, or metadata commands when validation or
  planning depends on them.
- `dry_run_plan`: CLI JSON field containing the path to a machine-readable plan
  artifact when the command produces one.
- `output_declarations`: typed output declarations with `path`, `kind`,
  `stage`, `exists`, and `will_create_on_apply`.
- `commands`: argv arrays suitable for inspection and direct process execution
  by a caller. Do not serialize shell strings as the machine contract.
- `outputs`: declared artifact paths. Dry-runs should report outputs only after
  inputs and options validate.
- `warnings` / `preflight`: non-fatal system, encoder, or adapter notes when a
  command exposes them. Fatal validation still fails before output claims.

## Current Command State

| Command | Current dry-run behavior | Current CLI JSON contract | Notes |
| --- | --- | --- | --- |
| `cosmos process` | Writes `cosmos_process_dry_run.v1.json` plus ingest stage artifacts. With `--post-process`, declares crop outputs from planned ingest outputs without creating placeholder media files. | Includes `command`, `dry_run`, `count`, `outputs`, `run_artifact`, `dry_run_plan`, `stage_artifacts`, and `output_declarations`. | Square crop argv can be built from planned ingest outputs. Rect crop argv requires source dimensions, so the process plan records a warning and declares outputs; run `cosmos crop run --dry-run --json` after ingest for executable rect argv. |
| `cosmos ingest run` | Writes `cosmos_ingest_run.v1.json` and `cosmos_ingest_dry_run.v1.json`; plan entries include adapter/options metadata and executable ffmpeg argv arrays. | Includes `command`, `dry_run`, `count`, `outputs`, `run_artifact`, `dry_run_plan`, and `output_declarations`. | COSM dry-runs persist plan-local concat manifests under `.cosmos-dry-run/ingest/` so argv arrays do not point at deleted temp files. |
| `cosmos crop run` | Validates inputs/jobs, writes `cosmos_crop_run.v1.json` and `cosmos_crop_dry_run.json`, and declares output paths without creating empty placeholder MP4 files. | Includes `command`, `mode`, `dry_run`, `count`, `outputs`, `run_artifact`, `dry_run_plan`, and `output_declarations`. | Plan commands expose square and rect crop argv arrays for validated existing inputs. |
| `cosmos crop curated-views` | Validates curated-view specs, writes aggregate `cosmos_crop_run.v1.json` and `cosmos_crop_dry_run.json`, and declares per-view MP4 outputs without creating placeholder files. | Includes `command`, `dry_run`, `count`, `outputs`, `run_artifact`, `dry_run_plan`, and `output_declarations`. | The aggregate plan combines the per-view crop argv arrays instead of leaving only the last view's SDK plan. |
| `cosmos optimize run` | Writes `cosmos_optimize_run.v1.json` and `cosmos_optimize_dry_run.json`; planned entries include `input`, `output`, `mode`, and `command` argv. | Includes `command`, `mode`, `dry_run`, `count`, `outputs`, `run_artifact`, `dry_run_plan`, and `output_declarations`. | The optimize plan keeps its legacy `planned` list as command-specific detail while also exposing the v1 `commands` list. Dry-run transcode planning uses deterministic `libx264` unless the caller explicitly forces or profile-pins an encoder. |
| `cosmos crop preview` / `cosmos crop curated-views-preview` | Builds preview run metadata and per-clip `preview_plan.v1.json` paths without rendering images in dry-run mode. | Includes `run_artifact`, `clip_plans`, `sheets`, `stacked`, `outputs`, and `count`. | Preview plans are preview-render plans, not crop execution command plans. Keep that distinction explicit. |

## Target Shape

Media-execution commands invoked with `--dry-run --json` expose this shape:

```json
{
  "command": "cosmos <area> <verb>",
  "dry_run": true,
  "count": 1,
  "outputs": ["out/example.mp4"],
  "output_declarations": [
    {
      "path": "out/example.mp4",
      "kind": "video",
      "stage": "optimize",
      "exists": false,
      "will_create_on_apply": true
    }
  ],
  "run_artifact": "out/cosmos_<area>_run.v1.json",
  "dry_run_plan": "out/cosmos_<area>_dry_run.json"
}
```

The plan artifact uses schema `cosmos-dry-run-plan-v1`:

```json
{
  "schema": "cosmos-dry-run-plan-v1",
  "command": "cosmos optimize run",
  "side_effects": {
    "executes_media_processing": false,
    "creates_media_outputs": false,
    "writes_metadata": [
      "out/cosmos_optimize_run.v1.json",
      "out/cosmos_optimize_dry_run.json"
    ]
  },
  "inputs": [{"path": "in/example.mp4", "kind": "video", "stage": "optimize", "observed": true}],
  "outputs": [
    {
      "path": "out/example_optimized.mp4",
      "kind": "video",
      "stage": "optimize",
      "exists": false,
      "will_create_on_apply": true
    }
  ],
  "commands": [
    {
      "stage": "optimize",
      "name": "example.mp4",
      "argv": ["ffmpeg", "-i", "in/example.mp4", "..."],
      "inputs": ["in/example.mp4"],
      "outputs": ["out/example_optimized.mp4"]
    }
  ],
  "validation": []
}
```

Plan entries may include command-specific fields such as adapter name, crop
geometry, trim window, encoder choice, or filter graph. Those fields are
additional context; they do not replace `commands`/`command` when the plan is
meant to describe executable work.

## Follow-Up Scope

Follow-up work should stay narrow and evidence-led:

- Add JSON Schema files for `cosmos-dry-run-plan-v1` and stdout payload shapes.
- Decide whether `process` should gain a dedicated process run provenance
  artifact or continue exposing child-stage run artifacts.
- Add executable rect-crop argv to process aggregate dry-runs once planned
  ingest outputs carry dimensions.
- Keep preview plan fields separate from execution command plans.
- Extend exit-code contract tests where new failure modes are added.
