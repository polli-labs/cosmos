# ruff: noqa: I001
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# -----------------------------
# Shared helpers
# -----------------------------

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ffmpeg_version() -> dict[str, str]:
    ff = shutil.which("ffmpeg") or "ffmpeg"
    try:
        out = subprocess.run([ff, "-version"], capture_output=True, text=True, check=True)  # noqa: S603
        line0 = (out.stdout or "").splitlines()[0] if out.stdout else ""
        return {"version": line0.strip(), "path": ff}
    except Exception:
        return {"version": "unknown", "path": ff}


def ffprobe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    try:
        out = subprocess.run(  # noqa: S603
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,pix_fmt,color_space",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(out.stdout or "{}")
        s = (data.get("streams") or [{}])[0]
        w = int(s.get("width") or 0)
        h = int(s.get("height") or 0)
        pix = s.get("pix_fmt") or ""
        cs = s.get("color_space") or ""
        fps = 0.0
        if s.get("r_frame_rate") and s["r_frame_rate"] != "0/0":
            num, den = s["r_frame_rate"].split("/")
            fps = (float(num) / float(den)) if float(den) else 0.0
        return {"width": w, "height": h, "fps": fps, "pix_fmt": pix, "color_space": cs}
    except Exception:
        return {"width": 0, "height": 0}


def system_info() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        mem_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        mem_gb = 0.0
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split(" ")[0],
        "cpu_count": os.cpu_count() or 0,
        "memory_gb": mem_gb,
    }


def package_version(pkg: str = "cosmos") -> str:
    try:
        return pkg_version(pkg)
    except Exception:
        return "0.0.0"


# -----------------------------
# Models
# -----------------------------


class OutputFile(BaseModel):
    path: str
    sha256: str
    bytes: int


class VideoInfo(BaseModel):
    width: int
    height: int
    fps: float | None = None
    pix_fmt: str | None = None
    color_space: str | None = None


class IngestRun(BaseModel):
    schema_version: str = Field(default="1.0.0")
    ingest_run_id: str
    tool: str = Field(default="cosmos-ingest")
    version: str
    git: str | None = None
    time: str
    input_dir: str
    manifest: str | None = None
    output_dir: str
    encoders_preference: list[str] | None = None
    ffmpeg: dict[str, Any] | None = None
    system: dict[str, Any] | None = None
    options: dict[str, Any] | None = None


class ClipArtifact(BaseModel):
    schema_version: str = Field(default="1.0.0")
    clip_id: str
    ingest_run_id: str
    name: str | None = None
    time_ms: dict[str, float] | None = None
    frames: dict[str, int] | None = None
    output: OutputFile
    video: VideoInfo
    encode: dict[str, Any] | None = None
    env: dict[str, Any] | None = None


class CropRun(BaseModel):
    schema_version: str = Field(default="1.0.0")
    crop_run_id: str
    tool: str = Field(default="cosmos-crop")
    version: str
    git: str | None = None
    time: str
    output_dir: str
    ffmpeg: dict[str, Any] | None = None
    system: dict[str, Any] | None = None
    jobs: list[dict[str, Any]] | None = None


class CropView(BaseModel):
    schema_version: str = Field(default="1.0.0")
    view_id: str
    crop_run_id: str
    job_ref: str | None = None
    source: dict[str, Any]
    output: OutputFile
    video: VideoInfo
    crop: dict[str, Any] | None = None
    encode: dict[str, Any] | None = None
    env: dict[str, Any] | None = None


# -----------------------------
# Writers
# -----------------------------


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4()}"


def emit_ingest_run(
    *,
    output_dir: Path,
    input_dir: Path,
    manifest_path: Path | None,
    options: dict[str, Any] | None,
    encoders_preference: list[str] | None,
) -> tuple[str, Path]:
    run = IngestRun(
        ingest_run_id=new_id("ing"),
        version=package_version("cosmos"),
        time=_now_iso(),
        input_dir=str(input_dir),
        manifest=str(manifest_path) if manifest_path else None,
        output_dir=str(output_dir),
        encoders_preference=encoders_preference,
        ffmpeg=ffmpeg_version(),
        system=system_info(),
        options=options,
    )
    out = output_dir / "cosmos_ingest_run.v1.json"
    write_json(out, json.loads(run.model_dump_json()))
    return run.ingest_run_id, out


def emit_clip_artifact(
    *,
    ingest_run_id: str,
    clip_name: str,
    output_path: Path,
    encode_info: dict[str, Any] | None,
    time_ms: tuple[float, float] | None,
    frames: tuple[int, int] | None,
) -> Path:
    stats = output_path.stat()
    out_file = OutputFile(path=str(output_path), sha256=sha256_file(output_path), bytes=stats.st_size)
    vinfo = VideoInfo(**ffprobe_video(output_path))
    clip = ClipArtifact(
        clip_id=new_id("clip"),
        ingest_run_id=ingest_run_id,
        name=clip_name,
        time_ms={"t0": time_ms[0], "t1": time_ms[1]} if time_ms else None,
        frames={"start": frames[0], "end": frames[1]} if frames else None,
        output=out_file,
        video=vinfo,
        encode=encode_info,
        env={"ffmpeg": ffmpeg_version(), "system": system_info()},
    )
    out = output_path.with_suffix(output_path.suffix + ".cosmos_clip.v1.json")
    write_json(out, json.loads(clip.model_dump_json()))
    return out


def emit_crop_run(*, output_dir: Path, jobs: list[dict[str, Any]] | None) -> tuple[str, Path]:
    run = CropRun(
        crop_run_id=new_id("crop"),
        version=package_version("cosmos"),
        time=_now_iso(),
        output_dir=str(output_dir),
        ffmpeg=ffmpeg_version(),
        system=system_info(),
        jobs=jobs,
    )
    out = output_dir / "cosmos_crop_run.v1.json"
    write_json(out, json.loads(run.model_dump_json()))
    return run.crop_run_id, out


def emit_crop_view(
    *,
    crop_run_id: str,
    source_path: Path,
    output_path: Path,
    crop_spec: dict[str, Any],
    encode_info: dict[str, Any] | None,
    job_ref: str | None = None,
) -> Path:
    source = {"path": str(source_path), "sha256": sha256_file(source_path)}
    stats = output_path.stat()
    out_file = OutputFile(path=str(output_path), sha256=sha256_file(output_path), bytes=stats.st_size)
    vinfo = VideoInfo(**ffprobe_video(output_path))
    view = CropView(
        view_id=new_id("view"),
        crop_run_id=crop_run_id,
        job_ref=job_ref,
        source=source,
        output=out_file,
        video=vinfo,
        crop=crop_spec,
        encode=encode_info,
        env={"ffmpeg": ffmpeg_version(), "system": system_info()},
    )
    out = output_path.with_suffix(output_path.suffix + ".cosmos_view.v1.json")
    write_json(out, json.loads(view.model_dump_json()))
    return out


# -----------------------------
# Resolvers (for ibrida and tools)
# -----------------------------


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def list_clip_artifacts(dir_path: Path) -> list[dict[str, Any]]:
    return [_load_json(p) for p in sorted(dir_path.glob("*.mp4.cosmos_clip.v1.json"))]


def list_view_artifacts(dir_path: Path) -> list[dict[str, Any]]:
    return [_load_json(p) for p in sorted(dir_path.glob("*.mp4.cosmos_view.v1.json"))]


def map_artifacts_by_sha(dir_path: Path) -> dict[str, dict[str, Any]]:
    """Return mapping from output sha256 to artifact for both clip and view files.

    Keys are artifact["output"]["sha256"].
    """
    m: dict[str, dict[str, Any]] = {}
    for a in list_clip_artifacts(dir_path) + list_view_artifacts(dir_path):
        out = (a.get("output") or {})
        sha = out.get("sha256")
        if isinstance(sha, str):
            m[sha] = a
    return m


def find_clip_for_file(file_path: Path) -> dict[str, Any] | None:
    """Compute sha256(file) and search sibling .cosmos_clip.v1.json by sha.

    Returns the loaded artifact dict or None.
    """
    sha = sha256_file(file_path)
    for meta in list_clip_artifacts(file_path.parent):
        if ((meta.get("output") or {}).get("sha256")) == sha:
            return meta
    return None


def find_view_for_file(file_path: Path) -> dict[str, Any] | None:
    sha = sha256_file(file_path)
    for meta in list_view_artifacts(file_path.parent):
        if ((meta.get("output") or {}).get("sha256")) == sha:
            return meta
    return None
