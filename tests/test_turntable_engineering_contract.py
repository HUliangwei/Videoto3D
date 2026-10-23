from pathlib import Path


def test_app_routes_turntable_from_run_manifest_and_keeps_shared_tail():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "from pipeline.cli_commands_engineering import (" in app
    assert 'if capture_mode == "turntable":' in app
    assert 'run_sparse_engineering(resolved["colmap"], run_root)' in app
    assert 'turntable_stage_ready(run_root, "triangulate")' in app
    assert 'if key == "run.mesh":' in app
    assert 'if key == "run.glb":' in app
    assert 'if key == "view.glb":' in app


def test_debug_commands_follow_existing_run_command_grammar():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    for key in ("run.anchor", "run.pairs", "run.orbit", "run.triangulate"):
        assert 'if key == "{}":'.format(key) in app


def test_engineering_runtime_never_targets_research_workspace():
    root = Path(__file__).resolve().parents[1]
    engine = (root / "pipeline/workflows/turntable/engineering.py").read_text(encoding="utf-8")
    assert "workspace/research/turntable" not in engine
    assert "workspace\\research\\turntable" not in engine
    assert "assert_run_local_path" in engine


def test_run_mesh_refuses_stale_legacy_turntable_sparse():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    block = app.split("def run_mesh(resolved, options):", 1)[1].split("def _validate_glb_name", 1)[0]
    assert 'turntable_stage_ready(run_root, "triangulate")' in block
    assert "Run sparse first" in block
