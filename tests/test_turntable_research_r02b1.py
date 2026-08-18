import math
import numpy as np

from pipeline.workflows.turntable.pose.shared_geometry import (
    directed_angle_error_deg,
    estimate_shared_geometry,
    line_angle_error_deg,
    observable_transverse_orbit,
    prepare_shared_geometry_pair,
)
from pipeline.workflows.turntable.pose.single_axis import (
    axis_angle_rotation,
    normalize_axis,
)


def _project(k, points):
    pixels = (k @ points.T).T
    return pixels[:, :2] / pixels[:, 2:3]


def _make_pairs():
    rng = np.random.default_rng(42)
    k = np.array(
        [
            [820.0, 0.0, 360.0],
            [0.0, 815.0, 360.0],
            [0.0, 0.0, 1.0],
        ]
    )
    axis = normalize_axis([0.20, 0.95, 0.23])
    transverse = observable_transverse_orbit(
        axis,
        [1.0, 0.0, 0.0],
    )

    pairs = []
    for delta_deg in (
        1.7,
        2.8,
        4.2,
        5.6,
        6.9,
        8.0,
    ):
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
        pairs.append(
            prepare_shared_geometry_pair(
                _project(k, left_3d),
                _project(k, right_3d),
                k,
                delta_deg,
                max_points=100,
            )
        )
    return axis, transverse, pairs


def test_observable_transverse_removes_axis_and_scale():
    axis = normalize_axis([0.2, 0.9, 0.3])
    orbit = np.array([2.0, -1.0, 4.0])
    first = observable_transverse_orbit(
        axis,
        orbit,
    )
    second = observable_transverse_orbit(
        axis,
        7.0 * orbit + 11.0 * axis,
    )
    assert line_angle_error_deg(first, second) < 1e-8
    assert abs(float(np.dot(axis, first))) < 1e-10
    assert np.isclose(np.linalg.norm(first), 1.0)


def test_line_error_treats_sign_as_gauge():
    vector = normalize_axis([0.3, 0.4, 0.5])
    assert line_angle_error_deg(
        vector,
        -vector,
    ) < 1e-8


def test_shared_geometry_estimator_recovers_frame():
    gt_axis, gt_transverse, pairs = _make_pairs()
    result = estimate_shared_geometry(
        pairs,
        coarse_step_deg=30.0,
        top_k=8,
        keep_ratio=0.90,
    )
    assert (
        directed_angle_error_deg(
            result["axis"],
            gt_axis,
        )
        < 0.25
    )
    assert (
        line_angle_error_deg(
            result["transverse_orbit_direction"],
            gt_transverse,
        )
        < 0.35
    )
    assert result["objective_sampson_px"] < 0.02
    assert result["observable_dof"] == 3
