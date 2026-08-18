"""Run-local workspace and schema-v4 manifest helpers for Videoto3D V0.11."""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pipeline.capture_mode import DEFAULT_CAPTURE_MODE, normalize_capture_mode

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RUN_DIRS = (
    "source", "frames", "masks", "segmentation", "colmap",
    "mesh", "splat", "output", "quality", "logs",
)
LOG_DIRS = ("shared", "mesh", "splat")
SHARED_STAGES = ("extract", "mask", "sparse")
ROUTE_STAGES = {
    "mesh": ("dense", "reconstruct", "refine", "texture", "glb"),
    "splat": ("training", "cleanup", "ply"),
}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_run_id(run_id):
    run_id = str(run_id or "")
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            "Invalid run id {!r}. Use 1-64 characters: letters, digits, '.', '_' or '-'; "
            "the first character must be alphanumeric.".format(run_id)
        )
    return run_id


def resolve_run_root(runs_dir, run_id):
    return Path(runs_dir) / validate_run_id(run_id)


def _pending():
    return {"status": "pending"}


def _default_manifest(run_id):
    now = _now()
    return {
        "schema_version": 4,
        "videoto3d_version": "0.11",
        "run_id": run_id,
        "capture_mode": DEFAULT_CAPTURE_MODE,
        "created_at": now,
        "updated_at": now,
        "source": {},
        "shared": {stage: _pending() for stage in SHARED_STAGES},
        "routes": {
            route: {stage: _pending() for stage in stages}
            for route, stages in ROUTE_STAGES.items()
        },
    }


def _ensure_dirs(run_root):
    run_root = Path(run_root)
    for name in RUN_DIRS:
        (run_root / name).mkdir(parents=True, exist_ok=True)
    for name in LOG_DIRS:
        (run_root / "logs" / name).mkdir(parents=True, exist_ok=True)


def _merge_move(src, dst):
    src = Path(src); dst = Path(dst)
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.move(str(src), str(dst))
        return
    if src.is_dir() and dst.is_dir():
        for child in list(src.iterdir()):
            _merge_move(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            pass
        return
    # Preserve both if an unexpected collision exists.
    suffix = 1
    candidate = dst.with_name(dst.name + ".migrated{}".format(suffix))
    while candidate.exists():
        suffix += 1
        candidate = dst.with_name(dst.name + ".migrated{}".format(suffix))
    shutil.move(str(src), str(candidate))


def _migrate_flat_logs(run_root):
    logs = Path(run_root) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for group in LOG_DIRS:
        (logs / group).mkdir(parents=True, exist_ok=True)
    for path in list(logs.iterdir()):
        if path.is_dir():
            continue
        name = path.name.lower()
        if name.startswith(("openmvs", "blender")):
            group = "mesh"
        elif name.startswith("brush"):
            group = "splat"
        else:
            group = "shared"
        _merge_move(path, logs / group / path.name)


def _migrate_layout_v10(run_root, old_manifest):
    run_root = Path(run_root)
    mesh_root = run_root / "mesh"
    splat_root = run_root / "splat"
    mesh_root.mkdir(parents=True, exist_ok=True)
    splat_root.mkdir(parents=True, exist_ok=True)

    for old_name in ("mvs_colmap", "openmvs_masks", "openmvs", "blender"):
        _merge_move(run_root / old_name, mesh_root / old_name)

    legacy = splat_root / "legacy_v09"
    old_brush = run_root / "brush"
    if old_brush.exists():
        _merge_move(old_brush, legacy)

    old_stages = old_manifest.get("stages", {}) if isinstance(old_manifest, dict) else {}
    old_splat = old_stages.get("splat", {})
    rel = old_splat.get("path") if isinstance(old_splat, dict) else None
    if rel:
        old_ply = run_root / rel
        if old_ply.exists():
            legacy.mkdir(parents=True, exist_ok=True)
            target = legacy / old_ply.name
            if target.exists():
                target = legacy / (old_ply.stem + "_baseline" + old_ply.suffix)
            _merge_move(old_ply, target)

    _migrate_flat_logs(run_root)
    _ensure_dirs(run_root)


def _convert_to_v3(run_root, old):
    _migrate_layout_v10(run_root, old)
    run_id = old.get("run_id", Path(run_root).name)
    new = _default_manifest(run_id)
    new["created_at"] = old.get("created_at", new["created_at"])
    new["updated_at"] = old.get("updated_at", new["updated_at"])
    new["source"] = old.get("source", {}) if isinstance(old.get("source", {}), dict) else {}
    stages = old.get("stages", {}) if isinstance(old.get("stages", {}), dict) else {}
    for stage in SHARED_STAGES:
        if isinstance(stages.get(stage), dict):
            new["shared"][stage] = dict(stages[stage])

    old_mesh = stages.get("mesh", {}) if isinstance(stages.get("mesh"), dict) else {}
    if old_mesh.get("status") == "ready":
        new["routes"]["mesh"]["dense"] = {
            "status": "ready", "path": "mesh/openmvs/scene_dense.ply"
        }
        new["routes"]["mesh"]["reconstruct"] = {
            "status": "ready", "path": "mesh/openmvs/scene_mesh.ply"
        }
        new["routes"]["mesh"]["refine"] = {
            "status": "ready", "path": "mesh/openmvs/scene_refined.ply"
        }
        texture = dict(old_mesh)
        texture["status"] = "ready"
        for key in ("obj", "mtl", "dense_ply", "refined_ply"):
            value = texture.get(key)
            if isinstance(value, str):
                texture[key] = value.replace("openmvs/", "mesh/openmvs/")
        textures = texture.get("textures")
        if isinstance(textures, list):
            texture["textures"] = [
                item.replace("openmvs/", "mesh/openmvs/") if isinstance(item, str) else item
                for item in textures
            ]
        new["routes"]["mesh"]["texture"] = texture

    old_glb = stages.get("glb", {}) if isinstance(stages.get("glb"), dict) else {}
    if old_glb:
        new["routes"]["mesh"]["glb"] = dict(old_glb)

    old_splat = stages.get("splat", {}) if isinstance(stages.get("splat"), dict) else {}
    if old_splat.get("status") == "ready":
        new["migration"] = {
            "v09_splat": {
                "status": "preserved_as_legacy",
                "legacy_dir": "splat/legacy_v09",
                "note": "V0.10 requires object-only sparse initialization; retrain Splat route.",
            }
        }
    return new



def _convert_v3_to_v4(run_root, old):
    """Non-destructively upgrade V0.10 dual-route manifests to V0.11.

    A V0.10 final Splat PLY is the raw Brush result (no post-cleanup stage yet).
    Preserve it under splat/raw so V0.11 can run cleanup without retraining.
    """
    run_root = Path(run_root)
    new = dict(old)
    new["capture_mode"] = normalize_capture_mode(old.get("capture_mode", DEFAULT_CAPTURE_MODE))
    new["schema_version"] = 4
    new["videoto3d_version"] = "0.11"
    routes = new.setdefault("routes", {})
    old_splat = routes.get("splat", {}) if isinstance(routes.get("splat", {}), dict) else {}
    training = dict(old_splat.get("training", {})) if isinstance(old_splat.get("training", {}), dict) else _pending()
    object_sparse = old_splat.get("object_sparse", {}) if isinstance(old_splat.get("object_sparse", {}), dict) else {}
    if object_sparse:
        for key in (
            "report", "source_points", "kept_points", "removed_points",
            "foreground_ratio", "min_foreground_observations",
        ):
            if key in object_sparse and key not in training:
                training[key] = object_sparse[key]
        training["object_sparse"] = {
            key: value for key, value in object_sparse.items() if key != "status"
        }
    old_ply = old_splat.get("ply", {}) if isinstance(old_splat.get("ply", {}), dict) else {}
    run_id = new.get("run_id", run_root.name)
    raw_dir = run_root / "splat" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / (str(run_id) + "_raw.ply")
    rel = old_ply.get("path")
    if old_ply.get("status") == "ready" and rel:
        source = run_root / rel
        if source.exists() and not raw_path.exists():
            shutil.copy2(str(source), str(raw_path))
        if raw_path.exists():
            training["status"] = "ready"
            training["raw_path"] = str(raw_path.relative_to(run_root))
            try:
                training["raw_size_bytes"] = raw_path.stat().st_size
            except OSError:
                pass
    routes["splat"] = {
        "training": training if training else _pending(),
        "cleanup": _pending(),
        "ply": _pending(),
    }
    migration = new.setdefault("migration", {})
    migration["v10_splat"] = {
        "status": "raw_preserved_cleanup_required",
        "raw_path": str(raw_path.relative_to(run_root)) if raw_path.exists() else None,
        "note": "V0.10 PLY preserved as raw Brush output; V0.11 cleanup must run before final PLY is ready.",
    }
    _ensure_dirs(run_root)
    return new

def save_run_manifest(run_root, manifest):
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest)
    manifest["updated_at"] = _now()
    path = run_root / "run.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(temp), str(path))
    return manifest


def load_run_manifest(run_root):
    run_root = Path(run_root)
    path = run_root / "run.json"
    if not path.exists():
        raise FileNotFoundError("Run manifest not found: {}".format(path))
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError("Invalid run manifest: {}".format(path))

    schema = int(value.get("schema_version", 1))
    if schema < 3 or "shared" not in value or "routes" not in value:
        value = _convert_to_v3(run_root, value)
        # _convert_to_v3 uses the current default schema for legacy projects.
        return save_run_manifest(run_root, value)
    if schema == 3:
        value = _convert_v3_to_v4(run_root, value)
        return save_run_manifest(run_root, value)

    changed = False
    capture_mode = normalize_capture_mode(value.get("capture_mode", DEFAULT_CAPTURE_MODE))
    if value.get("capture_mode") != capture_mode:
        value["capture_mode"] = capture_mode; changed = True
    if value.get("schema_version") != 4:
        value["schema_version"] = 4; changed = True
    if value.get("videoto3d_version") != "0.11":
        value["videoto3d_version"] = "0.11"; changed = True
    shared = value.setdefault("shared", {})
    for stage in SHARED_STAGES:
        if stage not in shared:
            shared[stage] = _pending(); changed = True
    routes = value.setdefault("routes", {})
    for route, stages in ROUTE_STAGES.items():
        entries = routes.setdefault(route, {})
        for stage in stages:
            if stage not in entries:
                entries[stage] = _pending(); changed = True
    _ensure_dirs(run_root)
    if changed:
        return save_run_manifest(run_root, value)
    return value


def create_or_load_run(runs_dir, run_id):
    run_id = validate_run_id(run_id)
    run_root = resolve_run_root(runs_dir, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    _ensure_dirs(run_root)
    if (run_root / "run.json").exists():
        manifest = load_run_manifest(run_root)
    else:
        manifest = save_run_manifest(run_root, _default_manifest(run_id))
    return run_root, manifest


def update_capture_mode(run_root, capture_mode):
    """Set the Run capture method once; changing it after source/extract is forbidden."""
    manifest = load_run_manifest(run_root)
    requested = normalize_capture_mode(capture_mode)
    current = normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE))
    locked = bool(manifest.get("source")) or (
        manifest.get("shared", {}).get("extract", {}).get("status") == "ready"
    )
    if locked and requested != current:
        raise RuntimeError(
            "Run capture method is immutable after source import/extraction: "
            "{} -> {}".format(current, requested)
        )
    manifest["capture_mode"] = requested
    return save_run_manifest(run_root, manifest)

def update_run_source(run_root, original_input, local_source):
    manifest = load_run_manifest(run_root)
    manifest["source"] = {
        "original_input": str(Path(original_input)),
        "local_file": str(Path(local_source).relative_to(Path(run_root))),
    }
    return save_run_manifest(run_root, manifest)


def update_shared_stage(run_root, stage, status, **fields):
    if stage not in SHARED_STAGES:
        raise ValueError("Unknown shared stage: {}".format(stage))
    manifest = load_run_manifest(run_root)
    entry = {"status": str(status), "updated_at": _now()}
    entry.update(fields)
    manifest["shared"][stage] = entry
    return save_run_manifest(run_root, manifest)


def update_route_stage(run_root, route, stage, status, **fields):
    if route not in ROUTE_STAGES or stage not in ROUTE_STAGES[route]:
        raise ValueError("Unknown route stage: {}.{}".format(route, stage))
    manifest = load_run_manifest(run_root)
    entry = {"status": str(status), "updated_at": _now()}
    entry.update(fields)
    manifest["routes"][route][stage] = entry
    return save_run_manifest(run_root, manifest)


def invalidate_shared_stages(run_root, stages):
    manifest = load_run_manifest(run_root)
    for stage in stages:
        if stage not in SHARED_STAGES:
            raise ValueError("Unknown shared stage: {}".format(stage))
        manifest["shared"][stage] = {"status": "pending", "updated_at": _now()}
    return save_run_manifest(run_root, manifest)


def invalidate_route_stages(run_root, route, stages=None):
    if route not in ROUTE_STAGES:
        raise ValueError("Unknown route: {}".format(route))
    stages = tuple(stages or ROUTE_STAGES[route])
    manifest = load_run_manifest(run_root)
    for stage in stages:
        if stage not in ROUTE_STAGES[route]:
            raise ValueError("Unknown route stage: {}.{}".format(route, stage))
        manifest["routes"][route][stage] = {"status": "pending", "updated_at": _now()}
    return save_run_manifest(run_root, manifest)


def copy_source_into_run(run_root, input_path):
    run_root = Path(run_root)
    input_path = Path(input_path).expanduser()
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError("Input video not found: {}".format(input_path))
    source_dir = run_root / "source"; source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / input_path.name
    try:
        same = input_path.resolve() == target.resolve()
    except OSError:
        same = False
    if not same:
        for item in source_dir.iterdir():
            if item.is_file(): item.unlink()
            elif item.is_dir(): shutil.rmtree(item)
        shutil.copy2(str(input_path), str(target))
    return target


def shared_stage_status(manifest, stage):
    return manifest.get("shared", {}).get(stage, {}).get("status", "pending")


def route_stage_status(manifest, route, stage):
    return manifest.get("routes", {}).get(route, {}).get(stage, {}).get("status", "pending")


def _shared_summary(manifest):
    if all(shared_stage_status(manifest, s) == "ready" for s in SHARED_STAGES):
        return "READY"
    if shared_stage_status(manifest, "mask") == "ready": return "SPARSE PENDING"
    if shared_stage_status(manifest, "extract") == "ready": return "MASK PENDING"
    return "PENDING"


def _route_summary(manifest, route, shared_ready):
    stages = ROUTE_STAGES[route]
    values = [route_stage_status(manifest, route, s) for s in stages]
    terminal = "glb" if route == "mesh" else "ply"
    if route_stage_status(manifest, route, terminal) == "ready": return "COMPLETE"
    if not shared_ready: return "BLOCKED"
    if any(v == "ready" for v in values): return "IN PROGRESS"
    return "PENDING"


def run_overall_status(manifest):
    shared_ready = _shared_summary(manifest) == "READY"
    mesh = _route_summary(manifest, "mesh", shared_ready)
    splat = _route_summary(manifest, "splat", shared_ready)
    if mesh == "COMPLETE" and splat == "COMPLETE": return "complete"
    if mesh == "COMPLETE": return "mesh_complete"
    if splat == "COMPLETE": return "splat_complete"
    if shared_ready: return "shared_ready"
    return "created"


def list_run_summaries(runs_dir):
    runs_dir = Path(runs_dir)
    if not runs_dir.exists(): return []
    summaries = []
    for child in sorted(runs_dir.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or not (child / "run.json").exists(): continue
        try: manifest = load_run_manifest(child)
        except Exception: continue
        shared = _shared_summary(manifest)
        shared_ready = shared == "READY"
        summaries.append({
            "run_id": manifest.get("run_id", child.name),
            "capture_mode": normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE)),
            "status": run_overall_status(manifest),
            "frames": manifest.get("shared", {}).get("extract", {}).get("frame_count", "-"),
            "shared_status": shared,
            "mesh_status": _route_summary(manifest, "mesh", shared_ready),
            "splat_status": _route_summary(manifest, "splat", shared_ready),
            "updated_at": manifest.get("updated_at", ""),
        })
    return summaries


# Compatibility wrappers used by older internal code/tests while V0.10 app migrates.
def update_run_stage(run_root, stage, status, **fields):
    if stage in SHARED_STAGES:
        return update_shared_stage(run_root, stage, status, **fields)
    if stage == "mesh":
        result = None
        for sub in ("dense", "reconstruct", "refine", "texture"):
            result = update_route_stage(run_root, "mesh", sub, status, **(fields if sub == "texture" else {}))
        return result
    if stage == "glb": return update_route_stage(run_root, "mesh", "glb", status, **fields)
    if stage == "splat":
        result = update_route_stage(run_root, "splat", "training", status, **fields)
        result = update_route_stage(run_root, "splat", "cleanup", status, **fields)
        return update_route_stage(run_root, "splat", "ply", status, **fields)
    raise ValueError("Unknown run stage: {}".format(stage))


def invalidate_run_stages(run_root, stages):
    shared = [s for s in stages if s in SHARED_STAGES]
    if shared: invalidate_shared_stages(run_root, shared)
    for stage in stages:
        if stage == "mesh": invalidate_route_stages(run_root, "mesh", ("dense", "reconstruct", "refine", "texture"))
        elif stage == "glb": invalidate_route_stages(run_root, "mesh", ("glb",))
        elif stage == "splat": invalidate_route_stages(run_root, "splat")
    return load_run_manifest(run_root)
