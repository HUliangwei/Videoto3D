from pathlib import Path
import json
import pytest
from pipeline.workflows import get_capture_workflow

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_registry_has_only_meaningful_capture_names():
    orbit = get_capture_workflow("orbit_camera")
    turntable = get_capture_workflow("turntable")
    assert orbit.id == "orbit_camera"
    assert orbit.maturity == "stable"
    assert turntable.id == "turntable"
    assert turntable.maturity == "research"
    source = read("pipeline/workflows/registry.py").lower()
    assert "workflow_a" not in source
    assert "workflow_b" not in source

def test_orbit_workflow_uses_full_rgb_incremental_sfm(monkeypatch, tmp_path):
    import pipeline.workflows.orbit_camera.workflow as workflow
    captured = {}
    def fake(**kwargs):
        captured.update(kwargs)
        return {"frame_count": 10, "database": "db", "model": "model", "stats": {}}
    monkeypatch.setattr(workflow, "run_sparse_reconstruction", fake)
    result = workflow.run_sparse(
        colmap_path="colmap",
        frames_dir=tmp_path / "frames",
        masks_dir=tmp_path / "masks",
        colmap_dir=tmp_path / "colmap",
        logs_dir=tmp_path / "logs",
    )
    assert captured["mask_path"] is None
    assert result["pose_strategy"] == "incremental_sfm"
    assert result["mask_guided"] is False

def test_turntable_is_routed_to_isolated_research_workflow(monkeypatch, tmp_path):
    import pipeline.workflows.turntable.workflow as workflow
    calls = []
    monkeypatch.setattr(workflow, "validate_masks", lambda frames, masks: calls.append(("masks", frames, masks)))
    def fake(**kwargs):
        calls.append(("turntable", kwargs))
        return {
            "frame_count": 10,
            "database": "db",
            "model": "model",
            "stats": {},
            "turntable": {"pose_strategy": "legacy"},
        }
    monkeypatch.setattr(workflow, "run_turntable_reconstruction", fake)
    result = workflow.run_sparse(
        colmap_path="colmap",
        frames_dir=tmp_path / "frames",
        masks_dir=tmp_path / "masks",
        colmap_dir=tmp_path / "colmap",
        logs_dir=tmp_path / "logs",
    )
    assert calls[0][0] == "masks"
    assert calls[1][0] == "turntable"
    assert result["mask_guided"] is True
    assert result["pose_strategy"] == "legacy"

def test_capture_method_is_immutable_after_source_import(tmp_path):
    from pipeline.run_workspace import create_or_load_run, save_run_manifest, update_capture_mode
    run_root, _ = create_or_load_run(tmp_path, "demo")
    update_capture_mode(run_root, "turntable")
    manifest = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    manifest["source"] = {"local_file": "source/demo.mp4"}
    save_run_manifest(run_root, manifest)
    with pytest.raises(RuntimeError):
        update_capture_mode(run_root, "orbit_camera")

def test_canonical_entrypoint_is_project_named():
    assert (ROOT / "Videoto3D.py").exists()
    assert 'root / "Videoto3D.py"' in read("bootstrap.py")
    assert 'self.root / "Videoto3D.py"' in read("gui/control/server/jobs.py")
    assert "python Videoto3D.py gui" in read("README.md")

def test_frontend_routes_capture_methods_to_separate_views():
    router = read("gui/control/web/src/pages/RunDetailPage.tsx")
    orbit = read("gui/control/web/src/workflows/orbit-camera/OrbitCameraRunView.tsx")
    turntable = read("gui/control/web/src/workflows/turntable/TurntableRunView.tsx")
    panel = read("gui/control/web/src/components/NewRunPanel.tsx")
    assert "run.capture_mode === 'turntable'" in router
    assert "OrbitCameraRunView" in router
    assert "TurntableRunView" in router
    assert "full-RGB SfM" in orbit
    assert "TURNTABLE RESEARCH" in turntable
    assert "Capture Method" in panel
