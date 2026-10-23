"""Stable free-span alternating joint refinement for Turntable R0.2b-2.1.

Fixes the R0.2b-2 optimizer-level mismatch by using one robust trimmed-RMS
Sampson objective for all adjacent pairs, monotonic candidate acceptance,
best-state retention, and explicit termination reasons.

No GT pose, GT span, or forced 360-degree normalization is used.
"""

from __future__ import annotations

import math
import numpy as np

from .single_axis import normalize_axis, structured_essential_matrix
from .structured_fit import normalized_homogeneous, sampson_squared
from .shared_geometry import (
    estimate_shared_geometry,
    line_angle_error_deg,
    observable_geometry_frame,
)


def estimator_input_contract():
    return {
        "ground_truth_axis_used": False,
        "ground_truth_orbit_used": False,
        "ground_truth_angles_used": False,
        "ground_truth_span_used": False,
        "forced_360_degree_span": False,
        "one_direction_monotonic_prior": True,
    }


def prepare_joint_pair(left_points_px, right_points_px, intrinsics, max_points=160):
    left = np.asarray(left_points_px, dtype=np.float64)
    right = np.asarray(right_points_px, dtype=np.float64)
    k = np.asarray(intrinsics, dtype=np.float64)

    if left.ndim != 2 or left.shape[1] != 2 or left.shape != right.shape:
        raise ValueError("left/right points must be matching Nx2 arrays")
    if len(left) < 8:
        raise ValueError("at least 8 correspondences are required")
    if k.shape != (3, 3):
        raise ValueError("intrinsics must be 3x3")

    max_points = int(max_points)
    if max_points < 8:
        raise ValueError("max_points must be >= 8")
    if len(left) > max_points:
        indices = np.linspace(0, len(left) - 1, max_points, dtype=np.int64)
        left = left[indices]
        right = right[indices]

    return {
        "left_points_px": left,
        "right_points_px": right,
        "left_h": normalized_homogeneous(left, k),
        "right_h": normalized_homogeneous(right, k),
        "focal_px": 0.5 * (abs(float(k[0, 0])) + abs(float(k[1, 1]))),
        "count": int(len(left)),
    }


def _trimmed_pair_mean_sampson_squared(
    pair,
    axis,
    transverse_direction,
    angle_deg,
    keep_ratio=0.70,
):
    keep_ratio = float(keep_ratio)
    if not (0.25 <= keep_ratio <= 1.0):
        raise ValueError("keep_ratio must be in [0.25, 1.0]")

    essential = structured_essential_matrix(
        axis,
        transverse_direction,
        math.radians(float(angle_deg)),
    )
    squared = sampson_squared(essential, pair["left_h"], pair["right_h"])
    count = len(squared)
    keep = max(8, int(math.floor(count * keep_ratio)))
    keep = min(keep, count)
    trimmed = np.partition(squared, keep - 1)[:keep]
    return float(np.mean(trimmed))


def joint_objective_px(
    joint_pairs,
    axis,
    transverse_direction,
    deltas_deg,
    keep_ratio=0.70,
):
    """Unified robust objective used by all blocks and candidate acceptance."""
    deltas = np.asarray(deltas_deg, dtype=np.float64)
    if deltas.shape != (len(joint_pairs),):
        raise ValueError("deltas_deg must match pair count")
    if not np.all(np.isfinite(deltas)) or np.any(deltas <= 0.0):
        raise ValueError("deltas_deg must be finite and positive")

    pair_means = []
    focals = []
    for pair, angle_deg in zip(joint_pairs, deltas):
        pair_means.append(
            _trimmed_pair_mean_sampson_squared(
                pair,
                axis,
                transverse_direction,
                float(angle_deg),
                keep_ratio=keep_ratio,
            )
        )
        focals.append(float(pair["focal_px"]))

    normalized_rms = math.sqrt(max(0.0, float(np.mean(pair_means))))
    return normalized_rms * float(np.median(focals))


def fit_positive_structured_angle(
    pair,
    axis,
    transverse_direction,
    min_angle_deg=0.25,
    max_angle_deg=20.0,
    coarse_step_deg=0.25,
    keep_ratio=0.70,
):
    """Positive angle search minimizing the same trimmed-RMS pair term."""
    min_angle_deg = float(min_angle_deg)
    max_angle_deg = float(max_angle_deg)
    coarse_step_deg = float(coarse_step_deg)
    if not (0.0 < min_angle_deg < max_angle_deg and coarse_step_deg > 0.0):
        raise ValueError("invalid positive angle search range")

    focal_px = float(pair["focal_px"])

    def score(value):
        mean_sq = _trimmed_pair_mean_sampson_squared(
            pair,
            axis,
            transverse_direction,
            float(value),
            keep_ratio=keep_ratio,
        )
        return math.sqrt(max(0.0, mean_sq)) * focal_px

    values = np.arange(
        min_angle_deg,
        max_angle_deg + 0.5 * coarse_step_deg,
        coarse_step_deg,
        dtype=np.float64,
    )
    best_error, best_deg = min(
        [(score(value), float(value)) for value in values],
        key=lambda item: item[0],
    )

    for half_width, step in ((0.60, 0.05), (0.10, 0.01)):
        low = max(min_angle_deg, best_deg - half_width)
        high = min(max_angle_deg, best_deg + half_width)
        values = np.arange(low, high + 0.5 * step, step, dtype=np.float64)
        best_error, best_deg = min(
            [(score(value), float(value)) for value in values],
            key=lambda item: item[0],
        )

    return {
        "signed_angle_deg": float(best_deg),
        "trimmed_rms_sampson_px": float(best_error),
    }


def _geometry_pairs(joint_pairs, deltas_deg, indices):
    prepared = []
    for index in indices:
        pair = joint_pairs[int(index)]
        delta_deg = float(deltas_deg[int(index)])
        if delta_deg <= 0.0:
            raise ValueError("joint Turntable deltas must stay positive")
        prepared.append(
            {
                "left_h": pair["left_h"],
                "right_h": pair["right_h"],
                "delta_angle_rad": math.radians(delta_deg),
                "delta_angle_deg": delta_deg,
                "focal_px": pair["focal_px"],
                "count": pair["count"],
            }
        )
    return prepared


def _even_geometry_indices(pair_count, geometry_pair_count):
    pair_count = int(pair_count)
    geometry_pair_count = min(max(3, int(geometry_pair_count)), pair_count)
    return sorted(
        {
            int(value)
            for value in np.linspace(0, pair_count - 1, geometry_pair_count)
        }
    )


def _fit_all_angles(
    joint_pairs,
    axis,
    transverse_direction,
    min_angle_deg,
    max_angle_deg,
    keep_ratio,
):
    values = []
    residuals = []
    for pair in joint_pairs:
        estimate = fit_positive_structured_angle(
            pair,
            axis,
            transverse_direction,
            min_angle_deg=min_angle_deg,
            max_angle_deg=max_angle_deg,
            keep_ratio=keep_ratio,
        )
        values.append(estimate["signed_angle_deg"])
        residuals.append(estimate["trimmed_rms_sampson_px"])
    return (
        np.asarray(values, dtype=np.float64),
        np.asarray(residuals, dtype=np.float64),
    )


def _state(axis, transverse, deltas, objective):
    return {
        "axis": normalize_axis(axis).copy(),
        "transverse_orbit_direction": normalize_axis(transverse).copy(),
        "deltas_deg": np.asarray(deltas, dtype=np.float64).copy(),
        "joint_objective_sampson_px": float(objective),
    }


def _copy_state(state):
    return _state(
        state["axis"],
        state["transverse_orbit_direction"],
        state["deltas_deg"],
        state["joint_objective_sampson_px"],
    )


def alternating_joint_refinement(
    joint_pairs,
    initial_axis,
    initial_transverse_direction,
    initial_deltas_deg,
    geometry_pair_count=12,
    max_iterations=20,
    min_angle_deg=0.25,
    max_angle_deg=20.0,
    geometry_coarse_step_deg=30.0,
    geometry_top_k=8,
    geometry_keep_ratio=0.70,
    objective_improvement_epsilon_px=1e-6,
    angle_tolerance_deg=0.05,
    axis_tolerance_deg=0.05,
    patience=3,
):
    """Stable joint refinement with monotonic accepted objective."""
    if len(joint_pairs) < 3:
        raise ValueError("at least 3 pair observations are required")

    deltas = np.asarray(initial_deltas_deg, dtype=np.float64)
    if deltas.shape != (len(joint_pairs),):
        raise ValueError("initial_deltas_deg must match pair count")
    if not np.all(np.isfinite(deltas)) or np.any(deltas <= 0.0):
        raise ValueError("initial_deltas_deg must be finite and positive")

    initial_frame = observable_geometry_frame(
        initial_axis,
        initial_transverse_direction,
    )
    axis = normalize_axis(initial_frame[:, 2])
    transverse = normalize_axis(initial_frame[:, 0])

    geometry_indices = _even_geometry_indices(
        len(joint_pairs),
        geometry_pair_count,
    )

    current_objective = joint_objective_px(
        joint_pairs,
        axis,
        transverse,
        deltas,
        keep_ratio=geometry_keep_ratio,
    )
    current = _state(axis, transverse, deltas, current_objective)
    best = _copy_state(current)

    accepted_objective_history = [float(current_objective)]
    history = []
    stale_rounds = 0
    termination_reason = "max_iterations"

    epsilon = float(objective_improvement_epsilon_px)
    if epsilon < 0.0:
        raise ValueError("objective_improvement_epsilon_px must be >= 0")
    patience = max(1, int(patience))

    for iteration in range(int(max_iterations)):
        previous = _copy_state(current)
        accepted_blocks = []
        rejected_blocks = []

        # A1: angle proposal.
        angle_candidate, angle_residuals = _fit_all_angles(
            joint_pairs,
            current["axis"],
            current["transverse_orbit_direction"],
            min_angle_deg,
            max_angle_deg,
            geometry_keep_ratio,
        )
        angle_objective = joint_objective_px(
            joint_pairs,
            current["axis"],
            current["transverse_orbit_direction"],
            angle_candidate,
            keep_ratio=geometry_keep_ratio,
        )
        if angle_objective < current["joint_objective_sampson_px"] - epsilon:
            current = _state(
                current["axis"],
                current["transverse_orbit_direction"],
                angle_candidate,
                angle_objective,
            )
            accepted_blocks.append("angle_1")
        else:
            rejected_blocks.append("angle_1")

        # G: geometry proposal, evaluated on all adjacent pairs.
        prepared = _geometry_pairs(
            joint_pairs,
            current["deltas_deg"],
            geometry_indices,
        )
        geometry = estimate_shared_geometry(
            prepared,
            coarse_step_deg=geometry_coarse_step_deg,
            top_k=geometry_top_k,
            keep_ratio=geometry_keep_ratio,
        )
        geometry_objective = joint_objective_px(
            joint_pairs,
            geometry["axis"],
            geometry["transverse_orbit_direction"],
            current["deltas_deg"],
            keep_ratio=geometry_keep_ratio,
        )
        if geometry_objective < current["joint_objective_sampson_px"] - epsilon:
            current = _state(
                geometry["axis"],
                geometry["transverse_orbit_direction"],
                current["deltas_deg"],
                geometry_objective,
            )
            accepted_blocks.append("geometry")
        else:
            rejected_blocks.append("geometry")

        # A2: angle re-fit after any accepted geometry update.
        final_angle_candidate, final_residuals = _fit_all_angles(
            joint_pairs,
            current["axis"],
            current["transverse_orbit_direction"],
            min_angle_deg,
            max_angle_deg,
            geometry_keep_ratio,
        )
        final_angle_objective = joint_objective_px(
            joint_pairs,
            current["axis"],
            current["transverse_orbit_direction"],
            final_angle_candidate,
            keep_ratio=geometry_keep_ratio,
        )
        if final_angle_objective < current["joint_objective_sampson_px"] - epsilon:
            current = _state(
                current["axis"],
                current["transverse_orbit_direction"],
                final_angle_candidate,
                final_angle_objective,
            )
            accepted_blocks.append("angle_2")
        else:
            rejected_blocks.append("angle_2")

        if current["joint_objective_sampson_px"] < best["joint_objective_sampson_px"] - epsilon:
            best = _copy_state(current)

        accepted_objective_history.append(
            float(current["joint_objective_sampson_px"])
        )

        max_delta_change = float(
            np.max(np.abs(current["deltas_deg"] - previous["deltas_deg"]))
        )
        mean_delta_change = float(
            np.mean(np.abs(current["deltas_deg"] - previous["deltas_deg"]))
        )
        axis_change = float(
            line_angle_error_deg(previous["axis"], current["axis"])
        )
        objective_improvement = float(
            previous["joint_objective_sampson_px"]
            - current["joint_objective_sampson_px"]
        )

        if objective_improvement <= epsilon:
            stale_rounds += 1
        else:
            stale_rounds = 0

        history.append(
            {
                "iteration": int(iteration + 1),
                "span_deg": float(np.sum(current["deltas_deg"])),
                "joint_objective_sampson_px":
                    float(current["joint_objective_sampson_px"]),
                "best_joint_objective_sampson_px":
                    float(best["joint_objective_sampson_px"]),
                "objective_improvement_px": objective_improvement,
                "accepted_blocks": list(accepted_blocks),
                "rejected_blocks": list(rejected_blocks),
                "max_delta_change_deg": max_delta_change,
                "mean_delta_change_deg": mean_delta_change,
                "axis_line_change_deg": axis_change,
                "angle_1_median_trimmed_rms_px":
                    float(np.median(angle_residuals)),
                "angle_2_median_trimmed_rms_px":
                    float(np.median(final_residuals)),
                "geometry_selected_pair_objective_px":
                    float(geometry["objective_sampson_px"]),
                "stale_rounds": int(stale_rounds),
            }
        )

        stable = (
            max_delta_change <= float(angle_tolerance_deg)
            and axis_change <= float(axis_tolerance_deg)
        )
        if stable:
            termination_reason = "stable_state"
            break
        if stale_rounds >= patience:
            termination_reason = "objective_patience"
            break

    returned = _copy_state(best)

    return {
        "axis": returned["axis"],
        "transverse_orbit_direction":
            returned["transverse_orbit_direction"],
        "deltas_deg": returned["deltas_deg"],
        "span_deg": float(np.sum(returned["deltas_deg"])),
        "joint_objective_sampson_px":
            float(returned["joint_objective_sampson_px"]),
        "best_state_returned": True,
        "converged": termination_reason != "max_iterations",
        "termination_reason": termination_reason,
        "iteration_count": int(len(history)),
        "history": history,
        "accepted_joint_objective_history_px":
            accepted_objective_history,
        "geometry_pair_indices":
            [int(index) for index in geometry_indices],
        "input_contract": estimator_input_contract(),
    }
