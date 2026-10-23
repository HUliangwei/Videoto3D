import json
from pathlib import Path
import numpy as np

from pipeline.workflows.turntable.pose.global_orbit import (
    measurements_from_r03c,
    solve_global_orbit,
)


def _synthetic_report():
    true = np.asarray([3.0,4.0,5.0,6.0,7.0,5.0], dtype=float)
    theta = np.concatenate(([0.0], np.cumsum(true)))
    hypotheses = []
    for gap in (2,3):
        for left in range(len(theta)-gap):
            right = left + gap
            hypotheses.append({
                "left_index": left,
                "right_index": right,
                "gap": gap,
                "candidates": [{
                    "angle_deg": float(theta[right]-theta[left] + 0.03),
                    "residual_px": 0.08,
                    "confidence": 1.0,
                }],
            })
    # One good and one intentionally bad gap5-style observation.
    hypotheses.append({
        "left_index": 0, "right_index": 5, "gap": 5,
        "candidates": [{"angle_deg": float(theta[5]-theta[0]+0.05),
                        "residual_px": 0.10, "confidence": 1.0}],
    })
    hypotheses.append({
        "left_index": 1, "right_index": 6, "gap": 5,
        "candidates": [{"angle_deg": 55.0,
                        "residual_px": 8.0, "confidence": 1.0}],
    })
    return {"hypotheses": hypotheses}, true


def test_measurements_gate_bad_gap5():
    report, _ = _synthetic_report()
    result = measurements_from_r03c(report, include_gap5=True)
    accepted = result["measurements"]
    rejected = result["rejected"]
    assert any(m["gap"] == 5 for m in accepted)
    assert len(rejected) == 1
    assert rejected[0]["gap"] == 5
    assert rejected[0]["reason"] == "gap5_residual_outlier"


def test_global_orbit_is_positive_monotonic_and_free_span():
    report, true = _synthetic_report()
    measurements = measurements_from_r03c(report, include_gap5=True)["measurements"]
    result = solve_global_orbit(
        frame_count=len(true)+1,
        measurements=measurements,
        irls_iterations=6,
    )
    deltas = np.asarray(result["deltas_deg"])
    angles = np.asarray(result["angles_deg"])
    assert np.all(deltas > 0)
    assert np.all(np.diff(angles) > 0)
    assert abs(float(np.sum(deltas)) - float(np.sum(true))) < 0.5
    assert abs(float(np.sum(deltas)) - 360.0) > 300.0
    assert result["forced_360_degree_span"] is False


def test_uploaded_r03c_report_solves_near_previous_reliable_span():
    path = Path("/mnt/data/r03c_hypothesis_report.json")
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    m = measurements_from_r03c(report, include_gap5=True)
    result = solve_global_orbit(60, m["measurements"], irls_iterations=8)
    assert 280.0 < result["span_deg"] < 285.0
    assert result["monotonicity_violations"] == 0
