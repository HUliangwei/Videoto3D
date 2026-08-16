import json
from pathlib import Path
from tempfile import TemporaryDirectory

from gui.control.server.progress import build_progress_snapshot


def _manifest(run_root, *, frames=10, mask_ready=False, sparse_ready=False):
    shared = {
        "extract": {"status": "ready", "frame_count": frames},
        "mask": {"status": "ready" if mask_ready else "pending", "mask_count": frames if mask_ready else 0},
        "sparse": {"status": "ready" if sparse_ready else "pending"},
    }
    data = {
        "schema_version": 3,
        "shared": shared,
        "routes": {
            "mesh": {stage: {"status": "pending"} for stage in ("dense", "reconstruct", "refine", "texture", "glb")},
            "splat": {stage: {"status": "pending"} for stage in ("object_sparse", "training", "cleanup", "ply")},
        },
    }
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "run.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_mask_progress_uses_generated_mask_files_for_exact_percentage():
    with TemporaryDirectory() as td:
        run_root = Path(td) / "demo_001"
        _manifest(run_root, frames=10)
        (run_root / "frames").mkdir()
        (run_root / "masks").mkdir()
        for index in range(10):
            (run_root / "frames" / f"frame_{index:04d}.jpg").write_bytes(b"jpg")
        for index in range(4):
            (run_root / "masks" / f"frame_{index:04d}.jpg.png").write_bytes(b"png")

        progress = build_progress_snapshot(run_root, "mask", [], [], "running")

        assert progress["mode"] == "determinate"
        assert progress["label"] == "Generating SAM2 masks"
        assert progress["current"] == 4
        assert progress["total"] == 10
        assert progress["percent"] == 40.0
        assert progress["detail"] == "4 / 10 masks"
        assert [item["status"] for item in progress["stages"]] == ["done", "active", "pending"]


def test_splat_progress_uses_latest_brush_export_and_requested_steps():
    with TemporaryDirectory() as td:
        run_root = Path(td) / "demo_001"
        data = _manifest(run_root, frames=10, mask_ready=True, sparse_ready=True)
        data["routes"]["splat"]["object_sparse"] = {"status": "ready"}
        (run_root / "run.json").write_text(json.dumps(data), encoding="utf-8")
        exports = run_root / "splat" / "exports"
        exports.mkdir(parents=True)
        (exports / "demo_001_5000.ply").write_bytes(b"ply")
        (exports / "demo_001_10000.ply").write_bytes(b"ply")

        command = ["python", "app.py", "route", "splat", "--run", "demo_001", "--steps", "30000"]
        progress = build_progress_snapshot(run_root, "splat", command, [], "running")

        assert progress["mode"] == "determinate"
        assert progress["label"] == "Brush training"
        assert progress["current"] == 10000
        assert progress["total"] == 30000
        assert round(progress["percent"], 1) == 33.3
        assert progress["stage_key"] == "training"


def test_mesh_progress_is_stage_only_and_never_invents_percentage():
    with TemporaryDirectory() as td:
        run_root = Path(td) / "demo_001"
        _manifest(run_root, frames=10, mask_ready=True, sparse_ready=True)
        lines = [
            "[ROUTE][RUN ] Mesh Route: Dense → Reconstruct → Refine → Texture",
            "[2/6] OpenMVS InterfaceCOLMAP...",
            "[3/6] OpenMVS dense point cloud...",
            "[4/6] OpenMVS mesh reconstruction...",
        ]

        progress = build_progress_snapshot(run_root, "mesh", [], lines, "running")

        assert progress["mode"] == "stage"
        assert progress["percent"] is None
        assert progress["label"] == "Reconstructing mesh"
        assert progress["stage_key"] == "reconstruct"
        assert any(item["key"] == "reconstruct" and item["status"] == "active" for item in progress["stages"])
