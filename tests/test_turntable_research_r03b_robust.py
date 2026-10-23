import math
import numpy as np

from pipeline.workflows.turntable.pose.robust_multibaseline import (
    diagnose_graph_edges,
    gate_long_baseline_edges,
    robust_graph_weights,
    robust_graph_objective_px,
    trajectory_regularity_penalty,
    alternating_robust_multibaseline_refinement,
)
from pipeline.workflows.turntable.pose.multibaseline import (
    prepare_graph_edges,
)
from pipeline.workflows.turntable.pose.shared_geometry import (
    observable_transverse_orbit,
)
from pipeline.workflows.turntable.pose.single_axis import (
    axis_angle_rotation,
    normalize_axis,
)


def _project(k, points):
    pixels = (k @ points.T).T
    return pixels[:, :2] / pixels[:, 2:3]


def _raw_edge(k, axis, transverse, angle_deg, left, right, seed, corrupt=False):
    rng = np.random.default_rng(seed)
    rotation = axis_angle_rotation(axis, math.radians(float(angle_deg)))
    translation = transverse - rotation @ transverse
    left_3d = rng.uniform(
        [-0.8, -0.7, 3.2],
        [0.8, 0.7, 5.5],
        size=(120, 3),
    )
    right_3d = (rotation @ left_3d.T).T + translation
    left_px = _project(k, left_3d)
    right_px = _project(k, right_3d)
    if corrupt:
        # Deterministic correspondence corruption: shuffle right observations.
        right_px = right_px[np.roll(np.arange(len(right_px)), 19)]
    return {
        "left_index": left,
        "right_index": right,
        "gap": right - left,
        "left_points_px": left_px,
        "right_points_px": right_px,
        "feature_method": "SYNTHETIC",
        "raw_match_count": len(left_px),
    }


def _problem(include_bad_gap5=True):
    k = np.array(
        [
            [820.0, 0.0, 360.0],
            [0.0, 815.0, 360.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    axis = normalize_axis([0.20, 0.95, 0.23])
    transverse = observable_transverse_orbit(axis, [1.0, 0.0, 0.0])
    deltas = np.asarray([3.0, 4.0, 5.0, 6.0, 7.0, 5.0], dtype=np.float64)
    theta = np.concatenate(([0.0], np.cumsum(deltas)))
    raw = []
    seed = 10
    for gap in (1, 2, 3):
        for left in range(len(theta) - gap):
            right = left + gap
            raw.append(
                _raw_edge(
                    k, axis, transverse,
                    theta[right] - theta[left],
                    left, right, seed,
                )
            )
            seed += 1
    raw.append(
        _raw_edge(
            k, axis, transverse,
            theta[5] - theta[0],
            0, 5, seed,
            corrupt=include_bad_gap5,
        )
    )
    prepared = prepare_graph_edges(raw, k, max_points=100)
    return axis, transverse, deltas, prepared


def test_weighting_strategies_have_expected_family_mass():
    edges = [
        {"gap": 1}, {"gap": 1}, {"gap": 1}, {"gap": 1},
        {"gap": 2}, {"gap": 2},
        {"gap": 5},
    ]
    equal_edge = robust_graph_weights(edges, "equal_edge")
    assert np.allclose(equal_edge, np.ones(7) / 7.0)

    equal_family = robust_graph_weights(edges, "equal_family")
    assert abs(float(np.sum(equal_family[:4])) - 1/3) < 1e-12
    assert abs(float(np.sum(equal_family[4:6])) - 1/3) < 1e-12
    assert abs(float(equal_family[6]) - 1/3) < 1e-12

    sqrt_family = robust_graph_weights(edges, "sqrt_family")
    family_mass = [
        float(np.sum(sqrt_family[:4])),
        float(np.sum(sqrt_family[4:6])),
        float(sqrt_family[6]),
    ]
    ratio = np.asarray(family_mass) / family_mass[-1]
    assert np.allclose(ratio, [2.0, math.sqrt(2.0), 1.0], atol=1e-12)


def test_confidence_weighting_downweights_bad_diagnostic():
    edges = [{"gap": 1}, {"gap": 1}, {"gap": 5}]
    diagnostics = [
        {"confidence": 1.0},
        {"confidence": 1.0},
        {"confidence": 0.05},
    ]
    weights = robust_graph_weights(
        edges,
        "confidence_weighted",
        diagnostics=diagnostics,
    )
    assert weights[2] < weights[0] * 0.2
    assert abs(float(np.sum(weights)) - 1.0) < 1e-12


def test_diagnostics_and_gating_reject_corrupted_gap5_edge():
    axis, transverse, deltas, edges = _problem(include_bad_gap5=True)
    diagnostics = diagnose_graph_edges(
        edges,
        axis,
        transverse,
        deltas,
        keep_ratio=1.0,
        search_window_deg=4.0,
        search_step_deg=0.1,
    )
    gated = gate_long_baseline_edges(
        edges,
        diagnostics,
        trusted_max_gap=3,
    )
    assert len(gated["accepted_edges"]) == len(edges) - 1
    assert len(gated["rejected_edges"]) == 1
    rejected = gated["rejected_edges"][0]
    assert rejected["gap"] == 5
    assert rejected["reason"] in {
        "anchor_residual_outlier",
        "angle_disagreement_outlier",
        "multiple_diagnostic_outliers",
    }


def test_robust_objective_changes_when_bad_edge_is_downweighted():
    axis, transverse, deltas, edges = _problem(include_bad_gap5=True)
    diagnostics = diagnose_graph_edges(
        edges, axis, transverse, deltas,
        keep_ratio=1.0,
        search_window_deg=4.0,
        search_step_deg=0.2,
    )
    equal_family = robust_graph_weights(edges, "equal_family")
    confidence = robust_graph_weights(
        edges,
        "confidence_weighted",
        diagnostics=diagnostics,
    )
    score_equal = robust_graph_objective_px(
        edges, axis, transverse, deltas,
        weights=equal_family, keep_ratio=1.0,
    )
    score_conf = robust_graph_objective_px(
        edges, axis, transverse, deltas,
        weights=confidence, keep_ratio=1.0,
    )
    assert score_conf < score_equal


def test_trajectory_regularity_penalty_detects_pathological_redistribution():
    smooth = np.asarray([3.0, 4.0, 5.0, 6.0, 7.0, 5.0])
    pathological = np.asarray([0.05, 0.06, 0.05, 17.0, 10.0, 2.84])
    assert trajectory_regularity_penalty(pathological) > (
        5.0 * trajectory_regularity_penalty(smooth)
    )
    assert abs(float(np.sum(pathological)) - float(np.sum(smooth))) < 1e-12


def test_robust_solver_keeps_fixed_weight_objective_monotonic():
    axis, transverse, true_deltas, edges = _problem(include_bad_gap5=False)
    diagnostics = diagnose_graph_edges(
        edges,
        axis,
        transverse,
        true_deltas,
        keep_ratio=1.0,
        search_window_deg=2.0,
        search_step_deg=0.2,
    )
    weights = robust_graph_weights(
        edges,
        "confidence_weighted",
        diagnostics=[dict(item, confidence=1.0) for item in diagnostics],
    )
    initial = 1.04 * true_deltas
    result = alternating_robust_multibaseline_refinement(
        edges,
        axis,
        transverse,
        initial,
        weights,
        geometry_pair_count=8,
        max_iterations=3,
        keep_ratio=1.0,
        trajectory_step_schedule_deg=(0.25, 0.10, 0.05),
        trajectory_sweeps_per_step=2,
    )
    history = result["accepted_joint_objective_history_px"]
    assert all(
        right <= left + 1e-12
        for left, right in zip(history[:-1], history[1:])
    )
    assert result["best_state_returned"] is True
    assert np.all(result["deltas_deg"] > 0.0)
    assert (
        np.mean(np.abs(result["deltas_deg"] - true_deltas))
        < np.mean(np.abs(initial - true_deltas))
    )
