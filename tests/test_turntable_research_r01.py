
import math
import numpy as np

from pipeline.workflows.turntable.benchmark.metrics import (
    angle_sequence_metrics,
    axis_error_deg,
)
from pipeline.workflows.turntable.benchmark.profiles import generate_profile
from pipeline.workflows.turntable.pose.single_axis import (
    axis_angle_rotation,
    structured_essential_matrix,
    structured_relative_pose,
)


def test_axis_angle_rotation_preserves_axis_and_is_orthonormal():
    axis = np.array([0.2, 0.9, -0.3], dtype=np.float64)
    axis /= np.linalg.norm(axis)
    rotation = axis_angle_rotation(axis, math.radians(37.0))
    assert np.allclose(rotation @ axis, axis, atol=1e-10)
    assert np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-10)
    assert np.isclose(np.linalg.det(rotation), 1.0, atol=1e-10)


def test_structured_relative_pose_translation_is_induced_by_shared_orbit_vector():
    axis = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    orbit = np.array([0.35, 0.08, 1.2], dtype=np.float64)
    rotation, translation = structured_relative_pose(
        axis, orbit, math.radians(23.0)
    )
    assert np.allclose(translation, orbit - rotation @ orbit, atol=1e-12)


def test_structured_essential_matrix_has_epipolar_rank_two():
    essential = structured_essential_matrix(
        axis=[0.0, 1.0, 0.0],
        orbit_vector=[0.4, 0.1, 1.0],
        delta_angle_rad=math.radians(18.0),
    )
    singular = np.linalg.svd(essential, compute_uv=False)
    assert singular[0] > 1e-8
    assert singular[1] > 1e-8
    assert singular[2] < 1e-10


def test_nonuniform_280_profile_is_monotonic_and_has_exact_span():
    profile = generate_profile("nonuniform_280", frame_count=60)
    assert len(profile.angles_deg) == 60
    assert np.isclose(profile.angles_deg[0], 0.0)
    assert np.isclose(profile.angles_deg[-1], 280.0)
    assert np.all(np.diff(profile.angles_deg) > 0.0)
    assert np.std(np.diff(profile.angles_deg)) > 0.1


def test_uniform_360_profile_is_uniform_and_has_exact_span():
    profile = generate_profile("uniform_360", frame_count=61)
    increments = np.diff(profile.angles_deg)
    assert np.isclose(profile.angles_deg[-1], 360.0)
    assert np.allclose(increments, increments[0], atol=1e-12)


def test_angle_metrics_remove_global_offset_and_resolve_axis_sign_gauge():
    gt = np.array([0.0, 10.0, 23.0, 40.0], dtype=np.float64)
    prediction = -gt + 137.0
    metrics = angle_sequence_metrics(prediction, gt)
    assert metrics["orientation_sign"] == -1
    assert metrics["angle_mae_deg"] < 1e-10
    assert metrics["increment_mae_deg"] < 1e-10
    assert metrics["span_error_deg"] < 1e-10


def test_axis_error_treats_axis_sign_as_same_physical_axis():
    assert axis_error_deg([0.0, 1.0, 0.0], [0.0, -1.0, 0.0]) < 1e-10
