"""Read-only progress inference for local GUI jobs.

Progress is derived from trustworthy run-local evidence: generated files,
run.json stage readiness, requested Brush steps and emitted tool log markers.
No reconstruction algorithm state is mutated here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_BRUSH_EXPORT_RE = re.compile(r"_(\d+)\.ply$", re.IGNORECASE)
_GENERIC_ITER_RE = re.compile(r"(?:iter(?:ation)?|step|train)[^0-9]{0,24}(\d+)\s*(?:/|of)\s*(\d+)", re.IGNORECASE)
_GENERIC_FRACTION_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")


def _read_manifest(run_root):
    path = Path(run_root) / "run.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, TypeError):
        return {}


def _status(entry):
    return "done" if isinstance(entry, dict) and entry.get("status") == "ready" else "pending"


def _stage(key, label, status="pending"):
    return {"key": key, "label": label, "status": status}


def _set_active(stages, key):
    for item in stages:
        if item["key"] == key and item["status"] != "done":
            item["status"] = "active"
        elif item["status"] == "active":
            item["status"] = "pending"
    return stages


def _option(command, name, default=None):
    flag = "--" + name.replace("_", "-")
    values = list(command or [])
    try:
        index = values.index(flag)
        return values[index + 1]
    except (ValueError, IndexError):
        return default


def _finish(stages, terminal_status):
    if terminal_status == "succeeded":
        for item in stages:
            if item["status"] == "active":
                item["status"] = "done"
    elif terminal_status in ("failed", "cancelled"):
        for item in stages:
            if item["status"] == "active":
                item["status"] = "error" if terminal_status == "failed" else "cancelled"
    return stages


def _mask_progress(run_root, manifest, status):
    frames = sorted((run_root / "frames").glob("frame_*.jpg"))
    masks = sorted((run_root / "masks").glob("*.png"))
    total = len(frames) or int(manifest.get("shared", {}).get("extract", {}).get("frame_count") or 0)
    current = min(len(masks), total) if total else len(masks)
    stages = [
        _stage("extract", "Extract frames", _status(manifest.get("shared", {}).get("extract"))),
        _stage("mask", "SAM2 masks", _status(manifest.get("shared", {}).get("mask"))),
        _stage("sparse", "COLMAP sparse", _status(manifest.get("shared", {}).get("sparse"))),
    ]
    if status == "running":
        _set_active(stages, "mask")
    _finish(stages, status)
    percent = round(current * 100.0 / total, 1) if total else None
    return {
        "mode": "determinate" if total else "stage",
        "label": "Generating SAM2 masks" if status == "running" else "SAM2 masks",
        "detail": "{} / {} masks".format(current, total) if total else "{} masks".format(current),
        "current": current,
        "total": total or None,
        "percent": percent,
        "stage_key": "mask",
        "stages": stages,
    }


def _extract_progress(run_root, manifest, status):
    current = len(list((run_root / "frames").glob("frame_*.jpg")))
    stages = [
        _stage("extract", "Extract frames", _status(manifest.get("shared", {}).get("extract"))),
        _stage("mask", "SAM2 masks", _status(manifest.get("shared", {}).get("mask"))),
        _stage("sparse", "COLMAP sparse", _status(manifest.get("shared", {}).get("sparse"))),
    ]
    if status == "running":
        _set_active(stages, "extract")
    _finish(stages, status)
    return {
        "mode": "stage",
        "label": "Extracting frames" if status == "running" else "Frame extraction",
        "detail": "{} frames written".format(current),
        "current": current,
        "total": None,
        "percent": None,
        "stage_key": "extract",
        "stages": stages,
    }


def _mesh_progress(run_root, manifest, lines, status):
    route = manifest.get("routes", {}).get("mesh", {})
    shared_ready = manifest.get("shared", {}).get("sparse", {}).get("status") == "ready"
    stages = [
        _stage("shared", "Shared / COLMAP", "done" if shared_ready else "pending"),
        _stage("dense", "Dense cloud", _status(route.get("dense"))),
        _stage("reconstruct", "Reconstruct mesh", _status(route.get("reconstruct"))),
        _stage("refine", "Refine mesh", _status(route.get("refine"))),
        _stage("texture", "Texture mesh", _status(route.get("texture"))),
        _stage("glb", "Export GLB", _status(route.get("glb"))),
    ]
    text = "\n".join(lines or [])
    active = "shared"
    label = "Preparing Shared / COLMAP"
    markers = (
        ("[3/6] OpenMVS dense", "dense", "Building dense point cloud"),
        ("[4/6] OpenMVS mesh reconstruction", "reconstruct", "Reconstructing mesh"),
        ("[5/6] OpenMVS mesh refinement", "refine", "Refining mesh"),
        ("[6/6] OpenMVS mesh texturing", "texture", "Texturing mesh"),
        ("[ROUTE][RUN ] mesh.glb", "glb", "Exporting GLB"),
    )
    for marker, key, title in markers:
        if marker in text:
            active, label = key, title
    if status == "running":
        _set_active(stages, active)
    _finish(stages, status)
    completed = sum(1 for item in stages if item["status"] == "done")
    active_index = next((i + 1 for i, item in enumerate(stages) if item["status"] == "active"), None)
    step = active_index or completed or 1
    return {
        "mode": "stage",
        "label": label if status == "running" else "Mesh Route",
        "detail": "Step {} / {}".format(step, len(stages)),
        "current": step,
        "total": len(stages),
        "percent": None,
        "stage_key": active,
        "stages": stages,
    }


def _latest_brush_iteration(run_root, run_id):
    best = 0
    exports = run_root / "splat" / "exports"
    if exports.exists():
        for path in exports.glob("{}_*.ply".format(run_id)):
            match = _BRUSH_EXPORT_RE.search(path.name)
            if match:
                best = max(best, int(match.group(1)))
    return best


def _iteration_from_lines(lines, total):
    best = 0
    for line in list(lines or [])[-300:]:
        match = _GENERIC_ITER_RE.search(line)
        if match:
            current, reported_total = int(match.group(1)), int(match.group(2))
            if reported_total == total:
                best = max(best, current)
                continue
        for current_text, total_text in _GENERIC_FRACTION_RE.findall(line):
            if int(total_text) == total:
                best = max(best, int(current_text))
    return best


def _splat_progress(run_root, manifest, command, lines, status):
    route = manifest.get("routes", {}).get("splat", {})
    shared_ready = manifest.get("shared", {}).get("sparse", {}).get("status") == "ready"
    object_ready = (run_root / "splat" / "object_sparse_report.json").exists() or route.get("object_sparse", {}).get("status") == "ready"
    stages = [
        _stage("shared", "Shared / COLMAP", "done" if shared_ready else "pending"),
        _stage("object_sparse", "Object sparse", "done" if object_ready else "pending"),
        _stage("training", "Brush training", _status(route.get("training"))),
        _stage("cleanup", "Splat cleanup", _status(route.get("cleanup"))),
        _stage("ply", "Final PLY", _status(route.get("ply"))),
    ]
    text = "\n".join(lines or [])
    total = int(_option(command, "steps", 30000) or 30000)
    run_id = run_root.name
    current = max(_latest_brush_iteration(run_root, run_id), _iteration_from_lines(lines, total))

    if route.get("training", {}).get("status") != "ready":
        active, label = ("training", "Brush training") if object_ready or "Brush" in text else ("object_sparse", "Preparing object-only sparse")
    elif route.get("cleanup", {}).get("status") != "ready":
        active, label = "cleanup", "Cleaning background splats"
    else:
        active, label = "ply", "Finalizing Splat PLY"

    if "SAM2/COLMAP multi-view Splat Cleanup" in text:
        active, label = "cleanup", "Cleaning background splats"
    if status == "running":
        _set_active(stages, active)
    _finish(stages, status)

    if active == "training" and total > 0:
        current = min(current, total)
        percent = round(current * 100.0 / total, 1)
        detail = "{} / {} steps".format(current, total)
        mode = "determinate"
    else:
        percent = None
        mode = "stage"
        step = next((i + 1 for i, item in enumerate(stages) if item["key"] == active), 1)
        detail = "Step {} / {}".format(step, len(stages))
        current, total = step, len(stages)

    return {
        "mode": mode,
        "label": label if status == "running" else "Splat Route",
        "detail": detail,
        "current": current,
        "total": total,
        "percent": percent,
        "stage_key": active,
        "stages": stages,
    }


def build_progress_snapshot(run_root, kind, command=None, lines=None, status="running"):
    run_root = Path(run_root)
    manifest = _read_manifest(run_root)
    kind = str(kind or "").lower()
    if kind == "mask":
        return _mask_progress(run_root, manifest, status)
    if kind == "extract":
        return _extract_progress(run_root, manifest, status)
    if kind == "mesh":
        return _mesh_progress(run_root, manifest, lines or [], status)
    if kind == "splat":
        return _splat_progress(run_root, manifest, command or [], lines or [], status)
    return {
        "mode": "stage",
        "label": kind.replace("_", " ").title() or "Core job",
        "detail": status.upper(),
        "current": None,
        "total": None,
        "percent": None,
        "stage_key": kind or "job",
        "stages": [_stage(kind or "job", kind.replace("_", " ").title() or "Core job", "active" if status == "running" else "done")],
    }
