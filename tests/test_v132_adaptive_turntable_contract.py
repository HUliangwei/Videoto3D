from pathlib import Path


def test_turntable_runner_uses_adaptive_angle_estimator():
    source = Path("pipeline/turntable.py").read_text(encoding="utf-8")
    assert "estimate_adaptive_turntable_angles" in source
    assert "turntable_angle_report.json" in source
    assert "build_pose_records(" in source
    assert '"point_triangulator"' in source


def test_app_records_dynamic_pose_strategy():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'pose_strategy = turntable.get("pose_strategy", "adaptive_360_epipolar")' in source
    assert '"turntable_angle_report"' in source
    assert '"turntable_angle_valid_pair_ratio"' in source


def test_readme_documents_nonuniform_turntable_speed():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Adaptive Turntable Angle" in readme
    assert "不需要匀速" in readme
    assert "turntable_angle_report.json" in readme
    assert "Orbit Camera" in readme
    assert "Mesh Route" in readme
    assert "Splat Route" in readme
