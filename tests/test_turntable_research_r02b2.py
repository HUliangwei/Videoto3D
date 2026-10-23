import math
import numpy as np

from pipeline.workflows.turntable.pose.initialization import (
    aggregate_pose_hypotheses,
    rotation_angle_deg,
)
from pipeline.workflows.turntable.pose.joint_refine import (
    alternating_joint_refinement,
    estimator_input_contract,
    prepare_joint_pair,
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


def _synthetic_joint_problem():
    rng = np.random.default_rng(123)
    k = np.array(
        [
            [820.0, 0.0, 360.0],
            [0.0, 815.0, 360.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    axis = normalize_axis([0.20, 0.95, 0.23])
    transverse = observable_transverse_orbit(
        axis,
        [1.0, 0.0, 0.0],
    )
    true_deltas = np.asarray(
        [1.6, 2.3, 3.9, 5.1, 6.8, 7.5, 6.4, 4.4],
        dtype=np.float64,
    )

    pairs = []
    for delta_deg in true_deltas:
        rotation = axis_angle_rotation(
            axis,
            math.radians(delta_deg),
        )
        translation = (
            transverse
            - rotation @ transverse
        )
        left_3d = rng.uniform(
            [-0.9, -0.8, 3.2],
            [0.9, 0.8, 5.8],
            size=(120, 3),
        )
        right_3d = (
            (rotation @ left_3d.T).T
            + translation
        )
        left_px = _project(k, left_3d)
        right_px = _project(k, right_3d)
        pairs.append(
            prepare_joint_pair(
                left_px,
                right_px,
                k,
                max_points=100,
            )
        )

    initial_axis = normalize_axis(
        axis_angle_rotation(
            [1.0, 0.0, 0.0],
            math.radians(0.8),
        )
        @ axis
    )
    initial_transverse = (
        axis_angle_rotation(
            [0.0, 1.0, 0.0],
            math.radians(2.0),
        )
        @ transverse
    )
    initial_transverse = (
        initial_transverse
        - initial_axis
        * float(
            np.dot(
                initial_axis,
                initial_transverse,
            )
        )
    )
    initial_transverse = normalize_axis(
        initial_transverse
    )
    initial_deltas = (
        0.8 * true_deltas + 0.5
    )

    return (
        k,
        axis,
        transverse,
        true_deltas,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    )


def test_rotation_angle_deg_matches_axis_angle():
    rotation = axis_angle_rotation(
        [0.2, 0.9, 0.3],
        math.radians(7.25),
    )
    assert abs(
        rotation_angle_deg(rotation) - 7.25
    ) < 1e-9


def test_pose_aggregation_rejects_missing_pair_and_preserves_lines():
    axis = normalize_axis([0.2, 0.95, 0.23])
    transverse = observable_transverse_orbit(
        axis,
        [1.0, 0.0, 0.0],
    )
    hypotheses = []
    for pair_index, delta in (
        (0, 2.0),
        (1, 3.5),
        (3, 6.0),
    ):
        hypotheses.append(
            {
                "pair_index": pair_index,
                "accepted": True,
                "angle_deg": delta,
                "axis": (
                    axis
                    if pair_index != 1
                    else -axis
                ),
                "transverse_candidate": (
                    transverse
                    if pair_index != 3
                    else -transverse
                ),
                "pose_inliers": 30,
                "weight": 2.0 + pair_index,
            }
        )

    result = aggregate_pose_hypotheses(
        hypotheses,
        pair_count=4,
    )
    assert (
        line_angle_error_deg(
            result["axis"],
            axis,
        )
        < 1e-8
    )
    assert (
        line_angle_error_deg(
            result["transverse_orbit_direction"],
            transverse,
        )
        < 1e-8
    )
    assert result["fallback_pair_count"] == 1
    assert result["initial_deltas_deg"][2] > 0.0


def test_joint_refinement_recovers_free_span_pose():
    (
        _,
        axis,
        transverse,
        true_deltas,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    ) = _synthetic_joint_problem()

    result = alternating_joint_refinement(
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=6,
        max_iterations=2,
        min_angle_deg=0.25,
        max_angle_deg=12.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
    )

    assert (
        float(
            np.mean(
                np.abs(
                    result["deltas_deg"]
                    - true_deltas
                )
            )
        )
        < 0.08
    )
    assert (
        line_angle_error_deg(
            result["axis"],
            axis,
        )
        < 0.5
    )
    assert (
        line_angle_error_deg(
            result[
                "transverse_orbit_direction"
            ],
            transverse,
        )
        < 2.0
    )
    assert abs(
        result["span_deg"]
        - float(np.sum(true_deltas))
    ) < 0.5


def test_joint_refinement_does_not_force_360():
    (
        _,
        _,
        _,
        true_deltas,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    ) = _synthetic_joint_problem()

    result = alternating_joint_refinement(
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=6,
        max_iterations=1,
        min_angle_deg=0.25,
        max_angle_deg=12.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
    )
    assert result["span_deg"] < 60.0
    assert abs(result["span_deg"] - 360.0) > 250.0
    assert np.all(result["deltas_deg"] > 0.0)
    assert float(np.sum(true_deltas)) < 60.0


def test_r02b2_input_contract_is_gt_free_and_free_span():
    contract = estimator_input_contract()
    assert contract["ground_truth_axis_used"] is False
    assert contract["ground_truth_orbit_used"] is False
    assert contract["ground_truth_angles_used"] is False
    assert contract["ground_truth_span_used"] is False
    assert contract["forced_360_degree_span"] is False
    assert contract["one_direction_monotonic_prior"] is True
