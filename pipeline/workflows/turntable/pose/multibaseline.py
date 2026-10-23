"""Multi-baseline structured Turntable solver for R0.3a."""
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
from .joint_refine import alternating_joint_refinement


def _validate_deltas(deltas_deg):
    deltas = np.asarray(deltas_deg, dtype=np.float64)
    if deltas.ndim != 1 or len(deltas) < 1:
        raise ValueError("deltas_deg must be a non-empty 1-D sequence")
    if not np.all(np.isfinite(deltas)) or np.any(deltas <= 0.0):
        raise ValueError("deltas_deg must be finite and positive")
    return deltas


def cumulative_angles_deg(deltas_deg):
    deltas = _validate_deltas(deltas_deg)
    return np.concatenate(
        (np.asarray([0.0], dtype=np.float64), np.cumsum(deltas))
    )


def edge_angle_deg(deltas_deg, left_index, right_index):
    deltas = _validate_deltas(deltas_deg)
    left = int(left_index)
    right = int(right_index)
    if not (0 <= left < right <= len(deltas)):
        raise ValueError("edge indices are outside trajectory")
    return float(np.sum(deltas[left:right]))


def prepare_graph_edges(accepted_edges, intrinsics, max_points=160):
    k = np.asarray(intrinsics, dtype=np.float64)
    if k.shape != (3, 3) or not np.all(np.isfinite(k)):
        raise ValueError("intrinsics must be a finite 3x3 matrix")
    max_points = int(max_points)
    if max_points < 8:
        raise ValueError("max_points must be >= 8")

    focal_px = 0.5 * (
        abs(float(k[0, 0])) + abs(float(k[1, 1]))
    )
    prepared = []
    for raw in accepted_edges:
        left = np.asarray(raw["left_points_px"], dtype=np.float64)
        right = np.asarray(raw["right_points_px"], dtype=np.float64)
        if (
            left.ndim != 2
            or left.shape[1] != 2
            or left.shape != right.shape
            or len(left) < 8
        ):
            raise ValueError("graph edge points must be matching Nx2 with N>=8")
        if len(left) > max_points:
            indices = np.linspace(
                0, len(left) - 1, max_points, dtype=np.int64
            )
            left = left[indices]
            right = right[indices]

        left_index = int(raw["left_index"])
        right_index = int(raw["right_index"])
        if right_index <= left_index:
            raise ValueError("graph edges require right_index > left_index")

        prepared.append(
            {
                "left_index": left_index,
                "right_index": right_index,
                "gap": int(right_index - left_index),
                "left_points_px": left,
                "right_points_px": right,
                "left_h": normalized_homogeneous(left, k),
                "right_h": normalized_homogeneous(right, k),
                "focal_px": focal_px,
                "count": int(len(left)),
                "feature_method": raw.get("feature_method", "UNKNOWN"),
                "raw_match_count": int(
                    raw.get("raw_match_count", len(left))
                ),
            }
        )
    if not prepared:
        raise ValueError("at least one accepted graph edge is required")
    return prepared


def graph_gap_weights(prepared_edges):
    if not prepared_edges:
        raise ValueError("prepared_edges must be non-empty")
    gaps = [int(edge["gap"]) for edge in prepared_edges]
    families = sorted(set(gaps))
    family_mass = 1.0 / float(len(families))
    counts = {
        gap: sum(1 for value in gaps if value == gap)
        for gap in families
    }
    weights = np.asarray(
        [
            family_mass / float(counts[gap])
            for gap in gaps
        ],
        dtype=np.float64,
    )
    return weights / float(np.sum(weights))


def _edge_trimmed_mean_sampson_squared(
    edge,
    axis,
    transverse_direction,
    angle_deg,
    keep_ratio,
):
    keep_ratio = float(keep_ratio)
    if not (0.25 <= keep_ratio <= 1.0):
        raise ValueError("keep_ratio must be in [0.25, 1.0]")
    essential = structured_essential_matrix(
        axis,
        transverse_direction,
        math.radians(float(angle_deg)),
    )
    squared = sampson_squared(
        essential,
        edge["left_h"],
        edge["right_h"],
    )
    keep = max(8, int(math.floor(len(squared) * keep_ratio)))
    keep = min(keep, len(squared))
    trimmed = np.partition(squared, keep - 1)[:keep]
    return float(np.mean(trimmed))


def graph_joint_objective_px(
    prepared_edges,
    axis,
    transverse_direction,
    deltas_deg,
    keep_ratio=0.70,
):
    deltas = _validate_deltas(deltas_deg)
    weights = graph_gap_weights(prepared_edges)
    values = []
    focals = []
    for edge in prepared_edges:
        values.append(
            _edge_trimmed_mean_sampson_squared(
                edge,
                axis,
                transverse_direction,
                edge_angle_deg(
                    deltas,
                    edge["left_index"],
                    edge["right_index"],
                ),
                keep_ratio,
            )
        )
        focals.append(float(edge["focal_px"]))
    weighted_mean = float(
        np.dot(weights, np.asarray(values, dtype=np.float64))
    )
    return (
        math.sqrt(max(0.0, weighted_mean))
        * float(np.median(focals))
    )


def refine_graph_trajectory(
    prepared_edges,
    axis,
    transverse_direction,
    deltas_deg,
    keep_ratio=0.70,
    step_schedule_deg=(0.25, 0.10, 0.05, 0.02),
    max_sweeps_per_step=2,
    min_delta_deg=0.05,
    improvement_epsilon_px=1e-9,
):
    """Coordinate descent where each delta is constrained by every spanning edge."""
    deltas = _validate_deltas(deltas_deg).copy()
    steps = tuple(float(step) for step in step_schedule_deg)
    if not steps or any(step <= 0.0 for step in steps):
        raise ValueError("step_schedule_deg must contain positive values")
    max_sweeps_per_step = max(1, int(max_sweeps_per_step))
    min_delta_deg = float(min_delta_deg)

    weights = graph_gap_weights(prepared_edges)
    focal = float(
        np.median([float(edge["focal_px"]) for edge in prepared_edges])
    )
    costs = np.asarray(
        [
            _edge_trimmed_mean_sampson_squared(
                edge,
                axis,
                transverse_direction,
                edge_angle_deg(
                    deltas,
                    edge["left_index"],
                    edge["right_index"],
                ),
                keep_ratio,
            )
            for edge in prepared_edges
        ],
        dtype=np.float64,
    )
    weighted_sum = float(np.dot(weights, costs))
    evaluation_count = int(len(prepared_edges))
    accepted_updates = 0

    spanning = []
    for index in range(len(deltas)):
        spanning.append(
            [
                edge_index
                for edge_index, edge in enumerate(prepared_edges)
                if int(edge["left_index"]) <= index < int(edge["right_index"])
            ]
        )

    def objective_from_sum(value):
        return math.sqrt(max(0.0, float(value))) * focal

    current_objective = objective_from_sum(weighted_sum)

    for step in steps:
        for _ in range(max_sweeps_per_step):
            sweep_changed = False
            for delta_index in range(len(deltas)):
                affected = spanning[delta_index]
                if not affected:
                    continue

                best = None
                for sign in (-1.0, 1.0):
                    candidate_value = float(
                        deltas[delta_index] + sign * step
                    )
                    if candidate_value <= min_delta_deg:
                        continue

                    candidate_deltas = deltas.copy()
                    candidate_deltas[delta_index] = candidate_value
                    candidate_sum = weighted_sum
                    candidate_costs = {}

                    for edge_index in affected:
                        edge = prepared_edges[edge_index]
                        value = _edge_trimmed_mean_sampson_squared(
                            edge,
                            axis,
                            transverse_direction,
                            edge_angle_deg(
                                candidate_deltas,
                                edge["left_index"],
                                edge["right_index"],
                            ),
                            keep_ratio,
                        )
                        candidate_costs[edge_index] = value
                        candidate_sum += (
                            float(weights[edge_index])
                            * (value - float(costs[edge_index]))
                        )
                    evaluation_count += len(affected)
                    candidate_objective = objective_from_sum(candidate_sum)

                    if (
                        candidate_objective
                        < current_objective - float(improvement_epsilon_px)
                        and (
                            best is None
                            or candidate_objective < best[0]
                        )
                    ):
                        best = (
                            candidate_objective,
                            candidate_value,
                            candidate_sum,
                            candidate_costs,
                        )

                if best is not None:
                    (
                        current_objective,
                        deltas[delta_index],
                        weighted_sum,
                        changed_costs,
                    ) = best
                    for edge_index, value in changed_costs.items():
                        costs[edge_index] = value
                    accepted_updates += 1
                    sweep_changed = True

            if not sweep_changed:
                break

    return {
        "deltas_deg": deltas,
        "objective_sampson_px": float(current_objective),
        "evaluation_count": int(evaluation_count),
        "accepted_updates": int(accepted_updates),
    }


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


def _select_geometry_edges(prepared_edges, pair_count):
    pair_count = min(
        max(3, int(pair_count)),
        len(prepared_edges),
    )
    by_gap = {}
    for index, edge in enumerate(prepared_edges):
        by_gap.setdefault(int(edge["gap"]), []).append(index)

    selected = []
    families = sorted(by_gap)
    cursor = {gap: 0 for gap in families}
    while len(selected) < pair_count:
        progress = False
        for gap in families:
            indices = by_gap[gap]
            pos = cursor[gap]
            if pos >= len(indices):
                continue
            if len(indices) == 1:
                chosen_pos = 0
            else:
                remaining_slots = max(
                    1,
                    int(
                        math.ceil(
                            (pair_count - len(selected))
                            / float(len(families))
                        )
                    ),
                )
                chosen_pos = min(
                    len(indices) - 1,
                    int(
                        round(
                            pos
                            * (len(indices) - 1)
                            / float(max(1, remaining_slots))
                        )
                    ),
                )
            candidate = indices[chosen_pos]
            cursor[gap] += 1
            if candidate not in selected:
                selected.append(candidate)
                progress = True
                if len(selected) >= pair_count:
                    break
        if not progress:
            break

    if len(selected) < pair_count:
        for index in range(len(prepared_edges)):
            if index not in selected:
                selected.append(index)
                if len(selected) >= pair_count:
                    break
    return selected[:pair_count]


def _prepared_geometry_pairs(prepared_edges, deltas_deg, selected_indices):
    pairs = []
    for index in selected_indices:
        edge = prepared_edges[int(index)]
        angle_deg = edge_angle_deg(
            deltas_deg,
            edge["left_index"],
            edge["right_index"],
        )
        pairs.append(
            {
                "left_h": edge["left_h"],
                "right_h": edge["right_h"],
                "delta_angle_rad": math.radians(angle_deg),
                "delta_angle_deg": angle_deg,
                "focal_px": edge["focal_px"],
                "count": edge["count"],
            }
        )
    return pairs


def alternating_multibaseline_refinement(
    prepared_edges,
    initial_axis,
    initial_transverse_direction,
    initial_deltas_deg,
    geometry_pair_count=12,
    max_iterations=12,
    keep_ratio=0.70,
    geometry_coarse_step_deg=30.0,
    geometry_top_k=8,
    trajectory_step_schedule_deg=(0.25, 0.10, 0.05, 0.02),
    trajectory_sweeps_per_step=2,
    objective_improvement_epsilon_px=1e-6,
    angle_tolerance_deg=0.05,
    axis_tolerance_deg=0.05,
    patience=3,
):
    enabled_gaps = {int(edge["gap"]) for edge in prepared_edges}
    if enabled_gaps == {1}:
        baseline = alternating_joint_refinement(
            prepared_edges,
            initial_axis,
            initial_transverse_direction,
            initial_deltas_deg,
            geometry_pair_count=geometry_pair_count,
            max_iterations=max_iterations,
            geometry_coarse_step_deg=geometry_coarse_step_deg,
            geometry_top_k=geometry_top_k,
            geometry_keep_ratio=keep_ratio,
            objective_improvement_epsilon_px=objective_improvement_epsilon_px,
            angle_tolerance_deg=angle_tolerance_deg,
            axis_tolerance_deg=axis_tolerance_deg,
            patience=patience,
        )
        baseline = dict(baseline)
        baseline["geometry_edge_indices"] = [
            int(index)
            for index in baseline.get("geometry_pair_indices", [])
        ]
        baseline["solver_mode"] = "r02b21_adjacent_baseline"
        return baseline

    deltas = _validate_deltas(initial_deltas_deg)
    frame = observable_geometry_frame(
        initial_axis,
        initial_transverse_direction,
    )
    axis = normalize_axis(frame[:, 2])
    transverse = normalize_axis(frame[:, 0])

    current_score = graph_joint_objective_px(
        prepared_edges,
        axis,
        transverse,
        deltas,
        keep_ratio=keep_ratio,
    )
    current = _state(axis, transverse, deltas, current_score)
    best = _copy_state(current)
    accepted_history = [float(current_score)]
    history = []
    stale_rounds = 0
    termination_reason = "max_iterations"
    epsilon = float(objective_improvement_epsilon_px)
    patience = max(1, int(patience))
    geometry_indices = _select_geometry_edges(
        prepared_edges,
        geometry_pair_count,
    )

    for iteration in range(int(max_iterations)):
        previous = _copy_state(current)
        accepted_blocks = []
        rejected_blocks = []

        trajectory = refine_graph_trajectory(
            prepared_edges,
            current["axis"],
            current["transverse_orbit_direction"],
            current["deltas_deg"],
            keep_ratio=keep_ratio,
            step_schedule_deg=trajectory_step_schedule_deg,
            max_sweeps_per_step=trajectory_sweeps_per_step,
        )
        if (
            trajectory["objective_sampson_px"]
            < current["joint_objective_sampson_px"] - epsilon
        ):
            current = _state(
                current["axis"],
                current["transverse_orbit_direction"],
                trajectory["deltas_deg"],
                trajectory["objective_sampson_px"],
            )
            accepted_blocks.append("trajectory")
        else:
            rejected_blocks.append("trajectory")

        geometry_pairs = _prepared_geometry_pairs(
            prepared_edges,
            current["deltas_deg"],
            geometry_indices,
        )
        geometry = estimate_shared_geometry(
            geometry_pairs,
            coarse_step_deg=geometry_coarse_step_deg,
            top_k=geometry_top_k,
            keep_ratio=keep_ratio,
        )
        geometry_score = graph_joint_objective_px(
            prepared_edges,
            geometry["axis"],
            geometry["transverse_orbit_direction"],
            current["deltas_deg"],
            keep_ratio=keep_ratio,
        )
        if (
            geometry_score
            < current["joint_objective_sampson_px"] - epsilon
        ):
            current = _state(
                geometry["axis"],
                geometry["transverse_orbit_direction"],
                current["deltas_deg"],
                geometry_score,
            )
            accepted_blocks.append("geometry")
        else:
            rejected_blocks.append("geometry")

        if (
            current["joint_objective_sampson_px"]
            < best["joint_objective_sampson_px"] - epsilon
        ):
            best = _copy_state(current)

        accepted_history.append(
            float(current["joint_objective_sampson_px"])
        )
        max_delta_change = float(
            np.max(
                np.abs(
                    current["deltas_deg"]
                    - previous["deltas_deg"]
                )
            )
        )
        axis_change = float(
            line_angle_error_deg(
                previous["axis"],
                current["axis"],
            )
        )
        improvement = float(
            previous["joint_objective_sampson_px"]
            - current["joint_objective_sampson_px"]
        )
        if improvement <= epsilon:
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
                "objective_improvement_px": improvement,
                "accepted_blocks": list(accepted_blocks),
                "rejected_blocks": list(rejected_blocks),
                "max_delta_change_deg": max_delta_change,
                "axis_line_change_deg": axis_change,
                "trajectory_evaluation_count":
                    int(trajectory["evaluation_count"]),
                "trajectory_accepted_updates":
                    int(trajectory["accepted_updates"]),
                "geometry_selected_edge_count":
                    int(len(geometry_indices)),
                "stale_rounds": int(stale_rounds),
            }
        )

        if (
            max_delta_change <= float(angle_tolerance_deg)
            and axis_change <= float(axis_tolerance_deg)
        ):
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
        "accepted_joint_objective_history_px":
            accepted_history,
        "history": history,
        "geometry_edge_indices":
            [int(index) for index in geometry_indices],
        "solver_mode": "r03a_multibaseline",
    }
