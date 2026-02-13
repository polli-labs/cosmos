from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from enum import IntEnum
from pathlib import Path
from typing import Any

import typer


class ExitCode(IntEnum):
    SUCCESS = 0
    INVALID_USAGE = 2
    INPUT_VALIDATION_ERROR = 3
    FFMPEG_PRECHECK_ERROR = 4
    PROCESSING_ERROR = 5


def resolve_output_mode(*, json_out: bool, plain_out: bool) -> str:
    if json_out and plain_out:
        raise typer.BadParameter("Choose only one machine output mode: --json or --plain")
    if json_out:
        return "json"
    if plain_out:
        return "plain"
    return "human"


def can_prompt(*, no_input: bool) -> bool:
    return (not no_input) and sys.stdin.isatty()


def emit_paths(paths: Iterable[Path], *, mode: str) -> None:
    rendered = [str(p) for p in paths]
    if mode == "json":
        typer.echo(json.dumps(rendered, indent=2))
        return
    for item in rendered:
        typer.echo(item)


def emit_payload(payload: dict[str, Any], *, mode: str) -> None:
    if mode == "json":
        typer.echo(json.dumps(payload, indent=2))
        return
    if mode == "plain":
        outputs = payload.get("outputs")
        if isinstance(outputs, list):
            for item in outputs:
                typer.echo(str(item))
            return
    # Human mode should remain concise and rely on command-specific output.
    return


def info(msg: str) -> None:
    typer.echo(msg, err=True)


def fail(message: str, *, code: ExitCode) -> None:
    typer.secho(f"error: {message}", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=int(code))


def raise_mapped_exit(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError | ValueError):
        fail(str(exc), code=ExitCode.INPUT_VALIDATION_ERROR)
        return
    if isinstance(exc, RuntimeError):
        text = str(exc).lower()
        if "ffmpeg" in text or "ffprobe" in text or "encoder" in text:
            fail(str(exc), code=ExitCode.FFMPEG_PRECHECK_ERROR)
            return
        fail(str(exc), code=ExitCode.PROCESSING_ERROR)
        return
    if isinstance(exc, subprocess.CalledProcessError):
        fail(str(exc), code=ExitCode.PROCESSING_ERROR)
        return
    fail(str(exc), code=ExitCode.PROCESSING_ERROR)
