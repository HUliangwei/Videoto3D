"""Unified per-run quality reporting for Shared, Mesh Route and Splat Route."""

import json
from pathlib import Path

from pipeline.run_workspace import load_run_manifest
from pipeline.capture_mode import DEFAULT_CAPTURE_MODE, normalize_capture_mode
from pipeline.splat_cleanup import read_ply_element_counts, read_ply_vertex_count


def _safe_counts(path):
    path = Path(path)
    if not path.exists(): return {}
    try: return read_ply_element_counts(path)
    except Exception: return {}


def _pct(value):
    return "{:.1f}%".format(float(value) * 100.0)


def generate_quality_report(run_root):
    run_root = Path(run_root); manifest = load_run_manifest(run_root); run_id = manifest.get("run_id", run_root.name)
    shared = manifest.get("shared", {}); mesh = manifest.get("routes", {}).get("mesh", {}); splat = manifest.get("routes", {}).get("splat", {})
    sparse = shared.get("sparse", {}); frames = int(shared.get("extract", {}).get("frame_count") or sparse.get("frame_count") or 0)
    capture_mode = normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE))
    sparse_mask_guided = bool(sparse.get("mask_guided", capture_mode == "turntable"))
    registered = int(sparse.get("registered_images") or 0)
    registration_rate = (registered / frames) if frames else 0.0

    dense_counts = _safe_counts(run_root / "mesh" / "openmvs" / "scene_dense.ply")
    refined_counts = _safe_counts(run_root / "mesh" / "openmvs" / "scene_refined.ply")
    glb_path = run_root / mesh.get("glb", {}).get("path", "__missing__")
    cleanup_entry = splat.get("cleanup", {})
    raw_rel = splat.get("training", {}).get("raw_path")
    raw_path = run_root / raw_rel if raw_rel else run_root / "splat" / "raw" / (run_id + "_raw.ply")
    final_rel = splat.get("ply", {}).get("path")
    final_path = run_root / final_rel if final_rel else run_root / "output" / (run_id + "_splat.ply")
    raw_count = cleanup_entry.get("raw_splats")
    clean_count = cleanup_entry.get("clean_splats")
    if raw_count is None and raw_path.exists():
        try: raw_count = read_ply_vertex_count(raw_path)
        except Exception: raw_count = None
    if clean_count is None and final_path.exists():
        try: clean_count = read_ply_vertex_count(final_path)
        except Exception: clean_count = None
    removal_ratio = cleanup_entry.get("removal_ratio")
    if removal_ratio is None and raw_count and clean_count is not None:
        removal_ratio = (raw_count - clean_count) / raw_count

    report = {
        "run_id": run_id,
        "shared": {
            "capture_mode": capture_mode,
            "sparse_mask_guided": sparse_mask_guided,
            "frames": frames,
            "masks": int(shared.get("mask", {}).get("mask_count") or 0),
            "registered_images": registered,
            "registration_rate": registration_rate,
            "sparse_points": sparse.get("points3D"),
            "mean_reprojection_error": sparse.get("mean_reprojection_error"),
        },
        "mesh_route": {
            "status": "ready" if mesh.get("glb", {}).get("status") == "ready" else "pending",
            "dense_points": dense_counts.get("vertex"),
            "final_vertices": refined_counts.get("vertex"),
            "final_faces": refined_counts.get("face"),
            "glb": mesh.get("glb", {}).get("path"),
            "glb_size_bytes": glb_path.stat().st_size if glb_path.exists() else mesh.get("glb", {}).get("size_bytes"),
        },
        "splat_route": {
            "status": "ready" if splat.get("ply", {}).get("status") == "ready" else "pending",
            "training_steps": splat.get("training", {}).get("steps"),
            "raw_splats": raw_count,
            "clean_splats": clean_count,
            "removed_splats": (raw_count - clean_count) if raw_count is not None and clean_count is not None else cleanup_entry.get("removed_splats"),
            "removal_ratio": removal_ratio,
            "cleanup_foreground_ratio": cleanup_entry.get("foreground_ratio"),
            "cleanup_min_views": cleanup_entry.get("min_views"),
            "ply": splat.get("ply", {}).get("path"),
            "ply_size_bytes": final_path.stat().st_size if final_path.exists() else splat.get("ply", {}).get("size_bytes"),
        },
    }
    quality_dir = run_root / "quality"; quality_dir.mkdir(parents=True, exist_ok=True)
    (quality_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    s = report["shared"]; m = report["mesh_route"]; p = report["splat_route"]
    lines = [
        "# Videoto3D Quality Report", "", "Run: `{}`".format(run_id), "",
        "## Shared", "",
        "- Capture mode: {}".format(s["capture_mode"]),
        "- SfM feature strategy: {}".format("SAM2 mask-guided" if s["sparse_mask_guided"] else "Full RGB"),
        "- Frames: {}".format(s["frames"]),
        "- SAM2 masks: {}".format(s["masks"]),
        "- COLMAP registered: {} / {} ({})".format(s["registered_images"], s["frames"], _pct(s["registration_rate"])),
        "- Sparse points: {}".format(s["sparse_points"] if s["sparse_points"] is not None else "-"),
        "- Mean reprojection error: {} px".format(s["mean_reprojection_error"] if s["mean_reprojection_error"] is not None else "-"),
        "", "## Mesh Route", "",
        "- Status: {}".format(m["status"]),
        "- Dense points: {}".format(m["dense_points"] if m["dense_points"] is not None else "-"),
        "- Final vertices: {}".format(m["final_vertices"] if m["final_vertices"] is not None else "-"),
        "- Final faces: {}".format(m["final_faces"] if m["final_faces"] is not None else "-"),
        "- GLB: {}".format(m["glb"] or "-"),
        "", "## Splat Route", "",
        "- Status: {}".format(p["status"]),
        "- Training steps: {}".format(p["training_steps"] if p["training_steps"] is not None else "-"),
        "- Raw splats: {}".format(p["raw_splats"] if p["raw_splats"] is not None else "-"),
        "- Clean splats: {}".format(p["clean_splats"] if p["clean_splats"] is not None else "-"),
        "- Removed splats: {}".format(p["removed_splats"] if p["removed_splats"] is not None else "-"),
        "- Removal ratio: {}".format(_pct(p["removal_ratio"]) if p["removal_ratio"] is not None else "-"),
        "- Cleanup threshold: ratio {} / min views {}".format(p["cleanup_foreground_ratio"] if p["cleanup_foreground_ratio"] is not None else "-", p["cleanup_min_views"] if p["cleanup_min_views"] is not None else "-"),
        "- Final PLY: {}".format(p["ply"] or "-"), "",
    ]
    (quality_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return report
