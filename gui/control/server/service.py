"""Videoto3D-specific GUI control data service.

This module may depend on run/quality/workspace concepts; `gui.viewer` remains
independent and reusable. Reconstruction execution is still delegated to core CLI jobs.
"""

import json
from pathlib import Path

from pipeline.env_manager import environment_python
from pipeline.run_workspace import list_run_summaries, load_run_manifest, validate_run_id


def _runs_dir(project_root):
    return Path(project_root) / "workspace" / "runs"


def _run_root(project_root, run_id):
    return _runs_dir(project_root) / validate_run_id(run_id)


def _read_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _asset_rel(manifest, run_id, kind):
    routes = manifest.get("routes", {})
    if kind == "glb":
        rel = routes.get("mesh", {}).get("glb", {}).get("path")
        return rel or "output/{}.glb".format(run_id)
    if kind == "splat":
        rel = routes.get("splat", {}).get("ply", {}).get("path")
        return rel or "output/{}_splat.ply".format(run_id)
    raise ValueError("Unsupported asset kind: {}".format(kind))


def resolve_run_asset(project_root, run_id, kind):
    run_root = _run_root(project_root, run_id)
    manifest = load_run_manifest(run_root)
    rel = _asset_rel(manifest, run_id, kind)
    candidate = (run_root / rel).resolve()
    root_resolved = run_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ValueError("Asset path escapes run root: {}".format(rel))
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("{} asset not found for run {}".format(kind, run_id))
    return candidate


def _asset_availability(project_root, run_id):
    values = {}
    for kind in ("glb", "splat"):
        try:
            resolve_run_asset(project_root, run_id, kind)
            values[kind] = True
        except (FileNotFoundError, ValueError, RuntimeError):
            values[kind] = False
    return values


def list_runs(project_root):
    rows = []
    for summary in list_run_summaries(_runs_dir(project_root)):
        item = dict(summary)
        item["assets"] = _asset_availability(project_root, item["run_id"])
        rows.append(item)
    return rows


def _load_quality(run_root):
    # Reading a detail page never regenerates quality; route jobs remain authoritative.
    return _read_json(Path(run_root) / "quality" / "report.json")


def _tool_paths(project_root):
    config = _read_json(Path(project_root) / "config" / "tools.json") or {}
    tools = config.get("tools", {}) if isinstance(config, dict) else {}
    result = {}
    for name in ("ffmpeg", "colmap", "openmvs", "brush", "blender"):
        entry = tools.get(name, {}) if isinstance(tools, dict) else {}
        result[name] = {
            "path": str(entry.get("path", "")) if isinstance(entry, dict) else "",
            "source": str(entry.get("source", "")) if isinstance(entry, dict) else "",
        }
    return result


def _paths_payload(project_root, run_root, manifest, run_id):
    project_root = Path(project_root).resolve()
    run_root = Path(run_root).resolve()
    mesh_glb = manifest.get("routes", {}).get("mesh", {}).get("glb", {}).get("path")
    splat_ply = manifest.get("routes", {}).get("splat", {}).get("ply", {}).get("path")
    return {
        "project": {
            "root": str(project_root),
            "workspace": str(project_root / "workspace"),
            "runtime": str(project_root / "runtime"),
        },
        "environments": {
            name: str(environment_python(project_root, name))
            for name in ("core", "seg", "gui")
        },
        "tools": _tool_paths(project_root),
        "run": {
            "root": str(run_root),
            "frames": str(run_root / "frames"),
            "masks": str(run_root / "masks"),
            "colmap": str(run_root / "colmap"),
            "mesh": str(run_root / "mesh"),
            "mesh_recipe": str(run_root / "mesh" / "openmvs" / "mesh_recipe.json"),
            "splat": str(run_root / "splat"),
            "splat_recipe": str(run_root / "splat" / "recipe.json"),
            "glb": str(run_root / mesh_glb) if mesh_glb else str(run_root / "output" / (run_id + ".glb")),
            "ply": str(run_root / splat_ply) if splat_ply else str(run_root / "output" / (run_id + "_splat.ply")),
        },
    }


def get_run_detail(project_root, run_id):
    run_root = _run_root(project_root, run_id)
    manifest = load_run_manifest(run_root)
    assets = {}
    availability = _asset_availability(project_root, run_id)
    if availability["glb"]:
        assets["glb"] = "/api/runs/{}/assets/glb".format(run_id)
    if availability["splat"]:
        assets["splat"] = "/api/runs/{}/assets/splat".format(run_id)
    return {
        "run_id": manifest.get("run_id", run_id),
        "root": str(run_root),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "source": manifest.get("source", {}),
        "shared": manifest.get("shared", {}),
        "routes": manifest.get("routes", {}),
        "quality": _load_quality(run_root),
        "assets": assets,
        "paths": _paths_payload(project_root, run_root, manifest, run_id),
    }


def resolve_first_frame(project_root, run_id):
    run_root = _run_root(project_root, run_id)
    frames = sorted((run_root / "frames").glob("frame_*.jpg"))
    if not frames:
        raise FileNotFoundError("No extracted frames for run {}".format(run_id))
    return frames[0]


def prepare_uploaded_source(project_root, run_id, filename):
    """Return a safe run-local source path for a new GUI upload."""
    run_id = validate_run_id(run_id)
    filename = str(filename or "")
    if not filename or Path(filename).name != filename or filename in (".", ".."):
        raise ValueError("Upload filename must be a plain filename")
    run_root = _run_root(project_root, run_id)
    if (run_root / "run.json").exists():
        manifest = load_run_manifest(run_root)
        source = manifest.get("source", {}) if isinstance(manifest.get("source", {}), dict) else {}
        extract = manifest.get("shared", {}).get("extract", {}).get("status")
        if source or extract == "ready":
            raise FileExistsError("Run {} already has source data".format(run_id))
    from pipeline.run_workspace import create_or_load_run
    run_root, _ = create_or_load_run(_runs_dir(project_root), run_id)
    source_dir = run_root / "source"
    for item in list(source_dir.iterdir()):
        if item.is_file():
            item.unlink()
    return source_dir / filename
