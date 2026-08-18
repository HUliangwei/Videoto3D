"""Shared observable Turntable geometry estimation for R0.2b-1.

R0.2b-1 receives signed relative angles from synthetic ground truth, but
it does NOT receive the ground-truth shared axis or orbit vector.

Only the epipolar-observable orbit component is estimated. If v is an
orbit vector and a is the unit rotation axis,

    v = v_perp + lambda a
    v - R(a, theta) v = v_perp - R(a, theta) v_perp

so the axial component lambda a is unobservable. Essential matrices are
defined only up to scale, therefore |v_perp| is also unobservable.

The estimator represents the observable shared geometry by one
right-handed frame Q = [u, a x u, a] in SO(3), where u is the unit
transverse orbit direction.
"""

from __future__ import annotations

import math
import numpy as np

from .single_axis import (
    axis_angle_rotation,
    normalize_axis,
    structured_essential_matrix,
)
from .structured_fit import normalized_homogeneous, sampson_squared


def _vector3(value, name):
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError("{} must be a finite 3-vector".format(name))
    return vector


def observable_transverse_orbit(axis, orbit_vector):
    """Return the unit epipolar-observable component of an orbit vector."""
    axis = normalize_axis(axis)
    orbit = _vector3(orbit_vector, "orbit_vector")
    transverse = orbit - axis * float(np.dot(axis, orbit))
    norm = float(np.linalg.norm(transverse))
    if norm <= 1e-12:
        raise ValueError("orbit_vector is parallel to the rotation axis")
    return transverse / norm


def line_angle_error_deg(left, right):
    """Angular error between unoriented 3-D lines; v and -v are equal."""
    left = normalize_axis(left)
    right = normalize_axis(right)
    dot = float(np.clip(abs(np.dot(left, right)), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def directed_angle_error_deg(left, right):
    left = normalize_axis(left)
    right = normalize_axis(right)
    dot = float(np.clip(np.dot(left, right), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def observable_geometry_frame(axis, transverse_direction):
    """Build right-handed observable frame Q=[u, a×u, a]."""
    axis = normalize_axis(axis)
    transverse = _vector3(
        transverse_direction,
        "transverse_direction",
    )
    transverse = transverse - axis * float(np.dot(axis, transverse))
    norm = float(np.linalg.norm(transverse))
    if norm <= 1e-12:
        raise ValueError(
            "transverse_direction must not be parallel to axis"
        )
    transverse = transverse / norm
    tangent = np.cross(axis, transverse)
    tangent = tangent / float(np.linalg.norm(tangent))
    return np.column_stack((transverse, tangent, axis))


def _rotation_x(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.asarray(
        [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]],
        dtype=np.float64,
    )


def _rotation_y(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.asarray(
        [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
        dtype=np.float64,
    )


def _rotation_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.asarray(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )


def _frame_from_euler_deg(yaw_deg, pitch_deg, roll_deg):
    yaw = math.radians(float(yaw_deg))
    pitch = math.radians(float(pitch_deg))
    roll = math.radians(float(roll_deg))
    return (
        _rotation_z(yaw)
        @ _rotation_y(pitch)
        @ _rotation_x(roll)
    )


def _canonicalize_transverse(transverse):
    transverse = normalize_axis(transverse)
    for value in transverse:
        if abs(float(value)) > 1e-12:
            return -transverse if value < 0.0 else transverse
    return transverse


def prepare_shared_geometry_pair(
    left_points_px,
    right_points_px,
    intrinsics,
    signed_delta_deg,
    max_points=120,
):
    """Normalize one pair and attach its known R0.2b-1 signed angle."""
    left = np.asarray(left_points_px, dtype=np.float64)
    right = np.asarray(right_points_px, dtype=np.float64)
    if (
        left.ndim != 2
        or left.shape[1] != 2
        or left.shape != right.shape
    ):
        raise ValueError(
            "left/right points must be matching Nx2 arrays"
        )
    if len(left) < 8:
        raise ValueError("at least 8 correspondences are required")

    max_points = int(max_points)
    if max_points < 8:
        raise ValueError("max_points must be >= 8")
    if len(left) > max_points:
        indices = np.linspace(
            0,
            len(left) - 1,
            max_points,
            dtype=np.int64,
        )
        left = left[indices]
        right = right[indices]

    k = np.asarray(intrinsics, dtype=np.float64)
    if k.shape != (3, 3):
        raise ValueError("intrinsics must be 3x3")

    delta_rad = math.radians(float(signed_delta_deg))
    if abs(delta_rad) <= 1e-8:
        raise ValueError(
            "R0.2b-1 pair angle is too close to zero"
        )

    return {
        "left_h": normalized_homogeneous(left, k),
        "right_h": normalized_homogeneous(right, k),
        "delta_angle_rad": float(delta_rad),
        "delta_angle_deg": float(signed_delta_deg),
        "focal_px": 0.5
        * (abs(float(k[0, 0])) + abs(float(k[1, 1]))),
        "count": int(len(left)),
    }


def shared_geometry_objective_px(
    axis,
    transverse_direction,
    prepared_pairs,
    keep_ratio=0.70,
):
    """Trimmed-RMS Sampson objective over all known-angle pairs."""
    if not prepared_pairs:
        raise ValueError("prepared_pairs cannot be empty")
    keep_ratio = float(keep_ratio)
    if not (0.25 <= keep_ratio <= 1.0):
        raise ValueError("keep_ratio must be in [0.25, 1.0]")

    try:
        frame = observable_geometry_frame(
            axis,
            transverse_direction,
        )
    except ValueError:
        return float("inf")

    transverse = frame[:, 0]
    axis = frame[:, 2]
    pair_means = []
    focals = []

    for pair in prepared_pairs:
        try:
            essential = structured_essential_matrix(
                axis,
                transverse,
                float(pair["delta_angle_rad"]),
            )
        except ValueError:
            return float("inf")

        squared = sampson_squared(
            essential,
            pair["left_h"],
            pair["right_h"],
        )
        count = len(squared)
        keep = max(
            8,
            int(math.floor(count * keep_ratio)),
        )
        keep = min(keep, count)
        trimmed = np.partition(
            squared,
            keep - 1,
        )[:keep]
        pair_means.append(float(np.mean(trimmed)))
        focals.append(float(pair["focal_px"]))

    normalized_rms = math.sqrt(
        max(0.0, float(np.mean(pair_means)))
    )
    return normalized_rms * float(np.median(focals))


def _search_directions():
    directions = []
    for x in (-1.0, 0.0, 1.0):
        for y in (-1.0, 0.0, 1.0):
            for z in (-1.0, 0.0, 1.0):
                if x == 0.0 and y == 0.0 and z == 0.0:
                    continue
                direction = np.asarray(
                    [x, y, z],
                    dtype=np.float64,
                )
                direction /= float(np.linalg.norm(direction))
                directions.append(direction)
    return tuple(directions)


_LOCAL_DIRECTIONS = _search_directions()


def _refine_frame(
    initial_frame,
    prepared_pairs,
    keep_ratio,
    refine_steps_deg,
    max_rounds_per_step,
):
    frame = np.asarray(
        initial_frame,
        dtype=np.float64,
    ).reshape(3, 3)
    score = shared_geometry_objective_px(
        frame[:, 2],
        frame[:, 0],
        prepared_pairs,
        keep_ratio=keep_ratio,
    )
    evaluations = 1

    for step_deg in refine_steps_deg:
        step_rad = math.radians(float(step_deg))
        for _ in range(int(max_rounds_per_step)):
            candidates = [(score, frame)]
            for direction in _LOCAL_DIRECTIONS:
                rotation = axis_angle_rotation(
                    direction,
                    step_rad,
                )
                candidate = rotation @ frame
                candidate_score = shared_geometry_objective_px(
                    candidate[:, 2],
                    candidate[:, 0],
                    prepared_pairs,
                    keep_ratio=keep_ratio,
                )
                evaluations += 1
                candidates.append(
                    (candidate_score, candidate)
                )

            next_score, next_frame = min(
                candidates,
                key=lambda item: item[0],
            )
            if next_score + 1e-12 < score:
                score = float(next_score)
                frame = next_frame
            else:
                break

    return score, frame, evaluations


def estimate_shared_geometry(
    prepared_pairs,
    coarse_step_deg=30.0,
    top_k=8,
    keep_ratio=0.70,
    refine_steps_deg=(
        10.0,
        5.0,
        2.0,
        1.0,
        0.5,
        0.2,
        0.05,
    ),
    max_rounds_per_step=80,
):
    """Estimate one shared axis + transverse orbit direction.

    Initialization enumerates a deterministic SO(3) Euler grid.
    Since u and -u produce Essential matrices differing only by sign,
    roll is searched only over [0, 180). The best seeds are refined
    by small rotations of the whole observable frame.
    """
    if len(prepared_pairs) < 3:
        raise ValueError(
            "at least 3 image pairs are required"
        )

    coarse_step_deg = float(coarse_step_deg)
    if not (5.0 <= coarse_step_deg <= 90.0):
        raise ValueError(
            "coarse_step_deg must be in [5, 90]"
        )
    top_k = max(1, int(top_k))

    yaw_values = np.arange(
        0.0,
        360.0,
        coarse_step_deg,
        dtype=np.float64,
    )
    pitch_values = np.arange(
        -90.0 + 0.5 * coarse_step_deg,
        90.0,
        coarse_step_deg,
        dtype=np.float64,
    )
    roll_values = np.arange(
        0.0,
        180.0,
        coarse_step_deg,
        dtype=np.float64,
    )

    coarse = []
    evaluations = 0
    for yaw in yaw_values:
        for pitch in pitch_values:
            for roll in roll_values:
                frame = _frame_from_euler_deg(
                    yaw,
                    pitch,
                    roll,
                )
                score = shared_geometry_objective_px(
                    frame[:, 2],
                    frame[:, 0],
                    prepared_pairs,
                    keep_ratio=keep_ratio,
                )
                evaluations += 1
                coarse.append((float(score), frame))

    coarse.sort(key=lambda item: item[0])
    seeds = coarse[: min(top_k, len(coarse))]

    refined = []
    for _, frame in seeds:
        score, result_frame, local_evaluations = (
            _refine_frame(
                frame,
                prepared_pairs,
                keep_ratio,
                tuple(
                    float(value)
                    for value in refine_steps_deg
                ),
                int(max_rounds_per_step),
            )
        )
        evaluations += local_evaluations
        refined.append(
            (float(score), result_frame)
        )

    best_score, best_frame = min(
        refined,
        key=lambda item: item[0],
    )
    axis = normalize_axis(best_frame[:, 2])
    transverse = _canonicalize_transverse(
        best_frame[:, 0]
    )

    return {
        "axis": axis,
        "transverse_orbit_direction": transverse,
        "objective_sampson_px": float(best_score),
        "coarse_candidate_count": int(len(coarse)),
        "refined_seed_count": int(len(seeds)),
        "evaluation_count": int(evaluations),
        "keep_ratio": float(keep_ratio),
        "observable_dof": 3,
    }
