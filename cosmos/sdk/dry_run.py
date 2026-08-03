from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DRY_RUN_PLAN_SCHEMA = "cosmos-dry-run-plan-v1"


def input_declaration(
    path: Path | str,
    *,
    kind: str,
    stage: str,
    observed: bool | None = None,
) -> dict[str, object]:
    p = Path(path)
    return {
        "path": str(p),
        "kind": kind,
        "stage": stage,
        "observed": p.exists() if observed is None else observed,
    }


def output_declaration(
    path: Path | str,
    *,
    kind: str,
    stage: str,
    exists: bool | None = None,
    will_create_on_apply: bool = True,
) -> dict[str, object]:
    p = Path(path)
    return {
        "path": str(p),
        "kind": kind,
        "stage": stage,
        "exists": p.exists() if exists is None else exists,
        "will_create_on_apply": will_create_on_apply,
    }


def command_declaration(
    *,
    stage: str,
    argv: list[str],
    inputs: list[Path | str] | None = None,
    outputs: list[Path | str] | None = None,
    name: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "stage": stage,
        "argv": argv,
    }
    if name is not None:
        payload["name"] = name
    if inputs is not None:
        payload["inputs"] = [str(p) for p in inputs]
    if outputs is not None:
        payload["outputs"] = [str(p) for p in outputs]
    return payload


def build_dry_run_plan(
    *,
    command: str,
    inputs: list[dict[str, object]],
    outputs: list[dict[str, object]],
    commands: list[dict[str, object]],
    metadata_writes: list[Path | str] | None = None,
    validation: list[dict[str, object]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    writes = [str(p) for p in metadata_writes or []]
    plan: dict[str, Any] = {
        "schema": DRY_RUN_PLAN_SCHEMA,
        "command": command,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "side_effects": {
            "executes_media_processing": False,
            "creates_media_outputs": False,
            "writes_metadata": writes,
        },
        "inputs": inputs,
        "outputs": outputs,
        "commands": commands,
        "validation": validation or [],
    }
    if extra:
        plan.update(extra)
    return plan


def write_dry_run_plan(path: Path, plan: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2))
    return path
