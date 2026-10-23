import math
import numpy as np

from pipeline.workflows.turntable.pose.joint_refine import (
    joint_objective_px,
    prepare_joint_pair,
)
from pipeline.workflows.turntable.pose.multibaseline import (
    alternating_multibaseline_refinement,
    cumulative_angles_deg,
    edge_angle_deg,
    graph_gap_weights,
    graph_joint_objective_px,
    prepare_graph_edges,
    refine_graph_trajectory,
)
from pipeline.workflows.turntable.pose.shared_geometry import (
    line_angle_error_deg,
    observable_transverse_orbit,
)
from pipeline.workflows.turntable.pose.single_axis import (
    axis_angle_rotation,
    normalize_axis,
)


def _project(k, points):
    pixels = (k @ points.T).T
    return pixels[:, :2] / pixels[:, 2:3]


def _raw_edge(k, axis, transverse, deltas, left, right, seed):
    rng = np.random.default_rng(seed)
    angle_deg = float(np.sum(deltas[left:right]))
    rotation = axis_angle_rotation(axis, math.radians(angle_deg))
    translation = transverse - rotation @ transverse
    left_3d = rng.uniform(
        [-0.8, -0.7, 3.2],
        [0.8, 0.7, 5.5],
        size=(100, 3),
    )
    right_3d = (rotation @ left_3d.T).T + translation
    return {
        "left_index": left,
        "right_index": right,
        "gap": right - left,
        "left_points_px": _project(k, left_3d),
        "right_points_px": _project(k, right_3d),
        "feature_method": "SYNTHETIC",
        "raw_match_count": 100,
    }


def _synthetic_graph(gaps=(1, 2, 3)):
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
    deltas = np.asarray([1.7, 2.6, 4.1, 5.3, 6.7, 7.4], dtype=np.float64)
    raw = []
    seed = 10
    frame_count = len(deltas) + 1
    for gap in gaps:
        for left in range(frame_count - gap):
            if gap == 5 and left % 5 != 0:
                continue
            raw.append(
                _raw_edge(
                    k, axis, transverse, deltas,
                    left, left + gap, seed,
                )
            )
            seed += 1
    prepared = prepare_graph_edges(raw, k, max_points=90)
    return k, axis, transverse, deltas, prepared


def test_edge_angle_is_sum_of_adjacent_deltas():
    deltas = np.asarray([2.0, 3.0, 4.0, 5.0])
    assert edge_angle_deg(deltas, 0, 3) == 9.0
    assert edge_angle_deg(deltas, 1, 4) == 12.0
    assert np.allclose(
        cumulative_angles_deg(deltas),
        [0.0, 2.0, 5.0, 9.0, 14.0],
    )


def test_gap_family_weights_have_equal_total_mass():
    prepared = [
        {"gap": 1}, {"gap": 1}, {"gap": 1},
        {"gap": 2}, {"gap": 2},
        {"gap": 5},
    ]
    weights = graph_gap_weights(prepared)
    assert abs(float(np.sum(weights[:3])) - 1.0 / 3.0) < 1e-12
    assert abs(float(np.sum(weights[3:5])) - 1.0 / 3.0) < 1e-12
    assert abs(float(weights[5]) - 1.0 / 3.0) < 1e-12
    assert abs(float(np.sum(weights)) - 1.0) < 1e-12


def test_multibaseline_objective_penalizes_scale_bias():
    _, axis, transverse, true_deltas, edges = _synthetic_graph()
    true_score = graph_joint_objective_px(
        edges, axis, transverse, true_deltas, keep_ratio=1.0
    )
    biased_score = graph_joint_objective_px(
        edges, axis, transverse, 1.05 * true_deltas, keep_ratio=1.0
    )
    assert true_score < 1e-7
    assert true_score < biased_score


def test_adjacent_only_graph_objective_matches_r02b21():
    k, axis, transverse, true_deltas, edges = _synthetic_graph(gaps=(1,))
    graph_score = graph_joint_objective_px(
        edges, axis, transverse, true_deltas, keep_ratio=0.90
    )
    adjacent_pairs = [
        prepare_joint_pair(
            edge["left_points_px"],
            edge["right_points_px"],
            k,
            max_points=90,
        )
        for edge in edges
    ]
    adjacent_score = joint_objective_px(
        adjacent_pairs,
        axis,
        transverse,
        true_deltas,
        keep_ratio=0.90,
    )
    assert abs(graph_score - adjacent_score) < 1e-10


def test_graph_trajectory_refinement_reduces_scale_bias():
    _, axis, transverse, true_deltas, edges = _synthetic_graph()
    initial = 1.05 * true_deltas
    before = float(np.mean(np.abs(initial - true_deltas)))
    result = refine_graph_trajectory(
        edges,
        axis,
        transverse,
        initial,
        keep_ratio=1.0,
        step_schedule_deg=(0.25, 0.10, 0.05, 0.02),
        max_sweeps_per_step=3,
    )
    after = float(np.mean(np.abs(result["deltas_deg"] - true_deltas)))
    assert after < before
    assert after < 0.10
    assert np.all(result["deltas_deg"] > 0.0)


def test_graph_refinement_keeps_free_span():
    _, axis, transverse, true_deltas, edges = _synthetic_graph()
    result = refine_graph_trajectory(
        edges,
        axis,
        transverse,
        1.03 * true_deltas,
        keep_ratio=1.0,
        max_sweeps_per_step=2,
    )
    assert float(np.sum(result["deltas_deg"])) < 60.0
    assert abs(float(np.sum(result["deltas_deg"])) - 360.0) > 250.0


def test_multibaseline_joint_solver_recovers_synthetic_pose():
    _, axis, transverse, true_deltas, edges = _synthetic_graph()
    initial_axis = normalize_axis(
        axis_angle_rotation([1.0, 0.0, 0.0], math.radians(0.7)) @ axis
    )
    initial_transverse = observable_transverse_orbit(
        initial_axis,
        axis_angle_rotation(
            [0.0, 1.0, 0.0], math.radians(1.0)
        ) @ transverse,
    )

    result = alternating_multibaseline_refinement(
        edges,
        initial_axis,
        initial_transverse,
        1.05 * true_deltas,
        geometry_pair_count=8,
        max_iterations=5,
        keep_ratio=1.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        trajectory_step_schedule_deg=(0.25, 0.10, 0.05, 0.02),
    )

    assert line_angle_error_deg(result["axis"], axis) < 0.5
    assert line_angle_error_deg(
        result["transverse_orbit_direction"], transverse
    ) < 1.0
    assert float(
        np.mean(np.abs(result["deltas_deg"] - true_deltas))
    ) < 0.12
    history = result["accepted_joint_objective_history_px"]
    assert all(
        right <= left + 1e-12
        for left, right in zip(history[:-1], history[1:])
    )
    assert result["best_state_returned"] is True


def test_gap1_multibaseline_solver_matches_frozen_r02b21_baseline():
    from pipeline.workflows.turntable.pose.joint_refine import (
        alternating_joint_refinement,
    )

    k, _, _, true_deltas, edges = _synthetic_graph(gaps=(1,))
    axis = normalize_axis([0.20, 0.95, 0.23])
    transverse = observable_transverse_orbit(axis, [1.0, 0.0, 0.0])
    initial_axis = normalize_axis(
        axis_angle_rotation([1.0, 0.0, 0.0], math.radians(0.7)) @ axis
    )
    initial_transverse = observable_transverse_orbit(
        initial_axis,
        axis_angle_rotation([0.0, 1.0, 0.0], math.radians(1.0)) @ transverse,
    )
    initial_deltas = 1.05 * true_deltas

    baseline_pairs = [
        prepare_joint_pair(
            edge["left_points_px"],
            edge["right_points_px"],
            k,
            max_points=90,
        )
        for edge in edges
    ]
    baseline = alternating_joint_refinement(
        baseline_pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=5,
        max_iterations=3,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
    )
    graph_result = alternating_multibaseline_refinement(
        edges,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=5,
        max_iterations=3,
        keep_ratio=0.90,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
    )

    assert np.allclose(graph_result["deltas_deg"], baseline["deltas_deg"])
    assert np.allclose(graph_result["axis"], baseline["axis"])
    assert np.allclose(
        graph_result["transverse_orbit_direction"],
        baseline["transverse_orbit_direction"],
    )
    assert abs(
        graph_result["joint_objective_sampson_px"]
        - baseline["joint_objective_sampson_px"]
    ) < 1e-12
