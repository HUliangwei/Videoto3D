from pathlib import Path


def test_v131_turntable_has_dedicated_known_pose_sparse_branch():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "from pipeline.turntable import run_turntable_reconstruction" in app
    assert 'if capture_mode == "turntable":' in app
    assert "run_turntable_reconstruction(" in app
    assert "run_sparse_reconstruction(" in app
    assert 'pose_strategy = turntable.get("pose_strategy", "adaptive_360_epipolar")' in app
    assert 'pose_strategy = "incremental_sfm"' in app


def test_turntable_module_uses_point_triangulator_and_both_directions():
    source = Path("pipeline/turntable.py").read_text(encoding="utf-8")
    assert '"point_triangulator"' in source
    assert '("cw", 1)' in source
    assert '("ccw", -1)' in source
    assert '"mapper"' not in source


def test_readme_states_manual_modes_and_full_turn_requirement():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Turntable Known-Pose" in readme
    assert "360" in readme
    assert "Orbit Camera" in readme
    assert "Mesh Route" in readme
    assert "Splat Route" in readme
