from pathlib import Path

import pytest

from tools.turntable_pose_ab_v1341 import (
    benchmark_paths,
    compare_sparse_stats,
    estimator_summary,
)


def test_benchmark_paths_are_isolated_from_shared_sparse(tmp_path):
    run_root = tmp_path / "workspace" / "runs" / "hlw_04"
    paths = benchmark_paths(run_root)

    assert paths["root"] == run_root / "colmap" / "diagnostics" / "pose_ab_v1341"
    assert paths["report"] == paths["root"] / "pose_ab_report.json"
    assert run_root / "colmap" / "sparse" / "0" not in paths.values()
    assert all("sparse\\0" not in str(value) and "sparse/0" not in str(value) for value in paths.values())


def test_estimator_summary_keeps_selected_sparse_metrics():
    candidates = [
        {"direction": "cw", "stats": {"points3D": 1200, "mean_track_length": 2.4, "mean_reprojection_error": 1.2}},
        {"direction": "ccw", "stats": {"points3D": 1500, "mean_track_length": 2.7, "mean_reprojection_error": 1.5}},
    ]
    summary = estimator_summary(
        name="constrained",
        span_deg=312.5,
        constraint_count=42,
        gap_coverage_ratio=0.82,
        candidates=candidates,
        selected=candidates[1],
    )

    assert summary["estimator"] == "constrained"
    assert summary["span_deg"] == pytest.approx(312.5)
    assert summary["constraint_count"] == 42
    assert summary["gap_coverage_ratio"] == pytest.approx(0.82)
    assert summary["best_direction"] == "ccw"
    assert summary["selected_stats"]["points3D"] == 1500
    assert summary["selected_stats"]["mean_track_length"] == pytest.approx(2.7)
    assert summary["selected_stats"]["mean_reprojection_error"] == pytest.approx(1.5)


def test_compare_sparse_stats_reports_constrained_deltas():
    legacy = {
        "selected_stats": {
            "points3D": 1000,
            "mean_track_length": 2.0,
            "mean_reprojection_error": 1.0,
        }
    }
    constrained = {
        "selected_stats": {
            "points3D": 1600,
            "mean_track_length": 2.5,
            "mean_reprojection_error": 1.2,
        }
    }

    comparison = compare_sparse_stats(legacy, constrained)

    assert comparison["points3D_delta"] == 600
    assert comparison["points3D_ratio"] == pytest.approx(1.6)
    assert comparison["mean_track_length_delta"] == pytest.approx(0.5)
    assert comparison["mean_reprojection_error_delta"] == pytest.approx(0.2)
    assert comparison["constrained_improves_points"] is True
    assert comparison["constrained_improves_track_length"] is True
