import math
import sys
import types

import numpy as np

from pipeline.workflows.turntable.pose.initialization import (
    _generic_pair_hypothesis,
)
from pipeline.workflows.turntable.pose.joint_refine import (
    alternating_joint_refinement,
    joint_objective_px,
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


def _problem():
    rng = np.random.default_rng(99)
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
        [1.7, 2.6, 4.1, 5.3, 6.7, 7.4],
        dtype=np.float64,
    )

    pairs = []
    for delta in true_deltas:
        rotation = axis_angle_rotation(
            axis,
            math.radians(float(delta)),
        )
        translation = transverse - rotation @ transverse
        left_3d = rng.uniform(
            [-0.8, -0.7, 3.2],
            [0.8, 0.7, 5.5],
            size=(100, 3),
        )
        right_3d = (
            rotation @ left_3d.T
        ).T + translation
        pairs.append(
            prepare_joint_pair(
                _project(k, left_3d),
                _project(k, right_3d),
                k,
                max_points=90,
            )
        )

    initial_axis = normalize_axis(
        axis_angle_rotation(
            [1.0, 0.0, 0.0],
            math.radians(0.8),
        )
        @ axis
    )
    initial_transverse = observable_transverse_orbit(
        initial_axis,
        transverse,
    )
    initial_deltas = 0.85 * true_deltas + 0.4

    return (
        axis,
        transverse,
        true_deltas,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    )


def test_zero_inlier_recover_pose_hypothesis_is_rejected(monkeypatch):
    angle = math.radians(5.0)
    rotation = np.array(
        [
            [math.cos(angle), 0.0, math.sin(angle)],
            [0.0, 1.0, 0.0],
            [-math.sin(angle), 0.0, math.cos(angle)],
        ],
        dtype=np.float64,
    )

    fake = types.SimpleNamespace()
    fake.RANSAC = 8
    fake.error = RuntimeError
    fake.findEssentialMat = lambda *args, **kwargs: (
        np.eye(3, dtype=np.float64),
        np.ones((12, 1), dtype=np.uint8),
    )
    fake.recoverPose = lambda *args, **kwargs: (
        0,
        rotation,
        np.array([[1.0], [0.0], [0.0]]),
        np.zeros((12, 1), dtype=np.uint8),
    )
    fake.Rodrigues = lambda matrix: (
        np.array([[0.0], [angle], [0.0]]),
        None,
    )

    monkeypatch.setitem(sys.modules, "cv2", fake)

    points = np.column_stack(
        (
            np.linspace(100.0, 300.0, 12),
            np.linspace(120.0, 260.0, 12),
        )
    )
    k = np.array(
        [
            [800.0, 0.0, 360.0],
            [0.0, 800.0, 360.0],
            [0.0, 0.0, 1.0],
        ]
    )

    result = _generic_pair_hypothesis(
        points,
        points + 1.0,
        k,
        pair_index=0,
        min_angle_deg=0.25,
        max_angle_deg=20.0,
        ransac_threshold_px=1.0,
    )
    assert result is None


def test_accepted_joint_objective_history_is_monotonic():
    (
        _,
        _,
        _,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    ) = _problem()

    result = alternating_joint_refinement(
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=5,
        max_iterations=6,
        min_angle_deg=0.25,
        max_angle_deg=10.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
    )

    history = result["accepted_joint_objective_history_px"]
    assert len(history) >= 2
    assert all(
        right <= left + 1e-12
        for left, right in zip(
            history[:-1],
            history[1:],
        )
    )


def test_solver_returns_best_state_and_records_termination():
    (
        axis,
        transverse,
        true_deltas,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    ) = _problem()

    result = alternating_joint_refinement(
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=5,
        max_iterations=8,
        min_angle_deg=0.25,
        max_angle_deg=10.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
        patience=2,
    )

    assert result["best_state_returned"] is True
    assert result["termination_reason"] in {
        "stable_state",
        "objective_patience",
        "max_iterations",
    }
    assert math.isclose(
        result["joint_objective_sampson_px"],
        min(result["accepted_joint_objective_history_px"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert line_angle_error_deg(
        result["axis"],
        axis,
    ) < 1.0
    assert line_angle_error_deg(
        result["transverse_orbit_direction"],
        transverse,
    ) < 2.0
    assert float(
        np.mean(
            np.abs(
                result["deltas_deg"] - true_deltas
            )
        )
    ) < 0.15


def test_joint_objective_matches_returned_state():
    (
        _,
        _,
        _,
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
    ) = _problem()

    result = alternating_joint_refinement(
        pairs,
        initial_axis,
        initial_transverse,
        initial_deltas,
        geometry_pair_count=5,
        max_iterations=3,
        min_angle_deg=0.25,
        max_angle_deg=10.0,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=6,
        geometry_keep_ratio=0.90,
    )

    score = joint_objective_px(
        pairs,
        result["axis"],
        result["transverse_orbit_direction"],
        result["deltas_deg"],
        keep_ratio=0.90,
    )
    assert math.isclose(
        score,
        result["joint_objective_sampson_px"],
        rel_tol=0.0,
        abs_tol=1e-12,
    )
