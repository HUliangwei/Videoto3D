"""Robust multi-baseline graph utilities for Turntable R0.3b.

R0.3a remains frozen. This module adds:
- fixed graph weighting strategies;
- GT-free edge diagnostics against a trusted anchor state;
- adaptive long-baseline gating;
- fixed-weight robust objective;
- optional weak trajectory regularity;
- stable weighted alternating refinement.
"""
from __future__ import annotations

import math
import numpy as np

from .multibaseline import (
    _edge_trimmed_mean_sampson_squared,
    _prepared_geometry_pairs,
    _select_geometry_edges,
    edge_angle_deg,
)
from .shared_geometry import (
    estimate_shared_geometry,
    line_angle_error_deg,
    observable_geometry_frame,
)
from .single_axis import normalize_axis


def _normalize_weights(weights, count):
    values = np.asarray(weights, dtype=np.float64)
    if values.shape != (int(count),):
        raise ValueError("weights must match edge count")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("weights must be finite and non-negative")
    total = float(np.sum(values))
    if total <= 0.0:
        raise ValueError("weights must have positive total mass")
    return values / total


def robust_graph_weights(prepared_edges, strategy, diagnostics=None):
    """Return fixed normalized edge weights for one ablation strategy."""
    if not prepared_edges:
        raise ValueError("prepared_edges must be non-empty")

    gaps = np.asarray(
        [int(edge["gap"]) for edge in prepared_edges],
        dtype=np.int64,
    )
    families = sorted(set(int(gap) for gap in gaps.tolist()))
    counts = {
        gap: int(np.sum(gaps == gap))
        for gap in families
    }
    strategy = str(strategy).strip().lower()

    if strategy == "equal_edge":
        weights = np.ones(len(prepared_edges), dtype=np.float64)

    elif strategy == "equal_family":
        weights = np.asarray(
            [1.0 / float(counts[int(gap)]) for gap in gaps],
            dtype=np.float64,
        )

    elif strategy == "sqrt_family":
        # Per-edge mass = 1/sqrt(n_g), hence family mass = sqrt(n_g).
        weights = np.asarray(
            [
                1.0 / math.sqrt(float(counts[int(gap)]))
                for gap in gaps
            ],
            dtype=np.float64,
        )

    elif strategy == "confidence_weighted":
        if diagnostics is None or len(diagnostics) != len(prepared_edges):
            raise ValueError(
                "confidence_weighted needs one diagnostic per edge"
            )
        base = np.asarray(
            [
                1.0 / math.sqrt(float(counts[int(gap)]))
                for gap in gaps
            ],
            dtype=np.float64,
        )
        confidence = np.asarray(
            [
                max(
                    1e-6,
                    min(1.0, float(record.get("confidence", 0.0))),
                )
                for record in diagnostics
            ],
            dtype=np.float64,
        )
        weights = base * confidence

    else:
        raise ValueError(
            "unknown weighting strategy: {}".format(strategy)
        )

    return _normalize_weights(weights, len(prepared_edges))


def _trimmed_rms_px(
    edge,
    axis,
    transverse_direction,
    angle_deg,
    keep_ratio,
):
    mean_sq = _edge_trimmed_mean_sampson_squared(
        edge,
        axis,
        transverse_direction,
        angle_deg,
        keep_ratio,
    )
    return (
        math.sqrt(max(0.0, float(mean_sq)))
        * float(edge["focal_px"])
    )


def diagnose_graph_edges(
    prepared_edges,
    axis,
    transverse_direction,
    deltas_deg,
    keep_ratio=0.70,
    search_window_deg=4.0,
    search_step_deg=0.10,
):
    """Measure each edge against a GT-free anchor trajectory and geometry."""
    search_window_deg = float(search_window_deg)
    search_step_deg = float(search_step_deg)
    if search_window_deg <= 0.0 or search_step_deg <= 0.0:
        raise ValueError("diagnostic search parameters must be positive")

    diagnostics = []
    for edge_index, edge in enumerate(prepared_edges):
        anchor_angle = edge_angle_deg(
            deltas_deg,
            edge["left_index"],
            edge["right_index"],
        )
        anchor_residual = _trimmed_rms_px(
            edge,
            axis,
            transverse_direction,
            anchor_angle,
            keep_ratio,
        )

        low = max(0.05, anchor_angle - search_window_deg)
        high = min(179.0, anchor_angle + search_window_deg)
        values = np.arange(
            low,
            high + 0.5 * search_step_deg,
            search_step_deg,
            dtype=np.float64,
        )
        scored = [
            (
                _trimmed_rms_px(
                    edge,
                    axis,
                    transverse_direction,
                    float(value),
                    keep_ratio,
                ),
                float(value),
            )
            for value in values
        ]
        best_residual, best_angle = min(
            scored,
            key=lambda item: item[0],
        )
        disagreement = abs(float(best_angle) - float(anchor_angle))
        residual_ratio = (
            float(anchor_residual)
            / max(float(best_residual), 1e-9)
        )

        diagnostics.append(
            {
                "edge_index": int(edge_index),
                "left_index": int(edge["left_index"]),
                "right_index": int(edge["right_index"]),
                "gap": int(edge["gap"]),
                "raw_match_count": int(
                    edge.get("raw_match_count", edge["count"])
                ),
                "anchor_angle_deg": float(anchor_angle),
                "anchor_trimmed_rms_sampson_px":
                    float(anchor_residual),
                "best_angle_deg": float(best_angle),
                "best_trimmed_rms_sampson_px":
                    float(best_residual),
                "angle_disagreement_deg": float(disagreement),
                "residual_ratio": float(residual_ratio),
            }
        )
    return diagnostics


def _robust_scale(values):
    values = np.asarray(values, dtype=np.float64)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    sigma = 1.4826 * mad
    return median, sigma


def gate_long_baseline_edges(
    prepared_edges,
    diagnostics,
    trusted_max_gap=3,
    residual_sigma=6.0,
    angle_sigma=6.0,
    residual_floor_px=0.25,
    angle_floor_deg=0.75,
):
    """Keep trusted short edges; gate long edges using trusted robust stats."""
    if len(prepared_edges) != len(diagnostics):
        raise ValueError("diagnostics must align with prepared_edges")

    trusted = [
        record
        for edge, record in zip(prepared_edges, diagnostics)
        if int(edge["gap"]) <= int(trusted_max_gap)
    ]
    if len(trusted) < 3:
        raise ValueError("at least 3 trusted diagnostics are required")

    trusted_residual = np.asarray(
        [
            float(record["anchor_trimmed_rms_sampson_px"])
            for record in trusted
        ],
        dtype=np.float64,
    )
    trusted_angle = np.asarray(
        [
            float(record["angle_disagreement_deg"])
            for record in trusted
        ],
        dtype=np.float64,
    )

    residual_median, residual_robust_sigma = _robust_scale(
        trusted_residual
    )
    angle_median, angle_robust_sigma = _robust_scale(trusted_angle)

    residual_q95 = float(np.quantile(trusted_residual, 0.95))
    angle_q95 = float(np.quantile(trusted_angle, 0.95))

    residual_threshold = max(
        float(residual_floor_px),
        residual_median
        + float(residual_sigma) * residual_robust_sigma,
        2.0 * residual_q95,
    )
    angle_threshold = max(
        float(angle_floor_deg),
        angle_median
        + float(angle_sigma) * angle_robust_sigma,
        2.0 * angle_q95,
    )

    accepted_edges = []
    accepted_diagnostics = []
    rejected = []

    for edge, record in zip(prepared_edges, diagnostics):
        gap = int(edge["gap"])
        if gap <= int(trusted_max_gap):
            accepted_edges.append(edge)
            accepted_diagnostics.append(dict(record, confidence=1.0))
            continue

        residual_bad = (
            float(record["anchor_trimmed_rms_sampson_px"])
            > residual_threshold
        )
        angle_bad = (
            float(record["angle_disagreement_deg"])
            > angle_threshold
        )

        if residual_bad or angle_bad:
            if residual_bad and angle_bad:
                reason = "multiple_diagnostic_outliers"
            elif residual_bad:
                reason = "anchor_residual_outlier"
            else:
                reason = "angle_disagreement_outlier"
            rejected.append(
                {
                    **record,
                    "reason": reason,
                    "residual_threshold_px":
                        float(residual_threshold),
                    "angle_threshold_deg":
                        float(angle_threshold),
                }
            )
            continue

        residual_scale = max(residual_threshold, 1e-9)
        angle_scale = max(angle_threshold, 1e-9)
        confidence = math.exp(
            -0.5
            * (
                float(record["anchor_trimmed_rms_sampson_px"])
                / residual_scale
            )
            ** 2
        ) * math.exp(
            -0.5
            * (
                float(record["angle_disagreement_deg"])
                / angle_scale
            )
            ** 2
        )

        accepted_edges.append(edge)
        accepted_diagnostics.append(
            dict(
                record,
                confidence=float(
                    max(0.02, min(1.0, confidence))
                ),
            )
        )

    return {
        "accepted_edges": accepted_edges,
        "accepted_diagnostics": accepted_diagnostics,
        "rejected_edges": rejected,
        "thresholds": {
            "trusted_max_gap": int(trusted_max_gap),
            "residual_threshold_px": float(residual_threshold),
            "angle_threshold_deg": float(angle_threshold),
            "trusted_residual_median_px":
                float(residual_median),
            "trusted_residual_robust_sigma_px":
                float(residual_robust_sigma),
            "trusted_angle_median_deg":
                float(angle_median),
            "trusted_angle_robust_sigma_deg":
                float(angle_robust_sigma),
        },
    }


def _huber(value, delta):
    value = abs(float(value))
    delta = float(delta)
    if value <= delta:
        return 0.5 * value * value / delta
    return value - 0.5 * delta


def trajectory_regularity_penalty(deltas_deg, huber_delta_deg=1.0):
    deltas = np.asarray(deltas_deg, dtype=np.float64)
    if deltas.ndim != 1 or len(deltas) < 3:
        return 0.0
    second = np.diff(deltas, n=2)
    return float(
        np.mean(
            [
                _huber(value, huber_delta_deg)
                for value in second
            ]
        )
    )


def robust_graph_objective_px(
    prepared_edges,
    axis,
    transverse_direction,
    deltas_deg,
    weights,
    keep_ratio=0.70,
    regularity_weight_px=0.0,
    regularity_huber_delta_deg=1.0,
):
    weights = _normalize_weights(weights, len(prepared_edges))
    costs = np.asarray(
        [
            _edge_trimmed_mean_sampson_squared(
                edge,
                axis,
                transverse_direction,
                edge_angle_deg(
                    deltas_deg,
                    edge["left_index"],
                    edge["right_index"],
                ),
                keep_ratio,
            )
            for edge in prepared_edges
        ],
        dtype=np.float64,
    )
    focal = float(
        np.median(
            [float(edge["focal_px"]) for edge in prepared_edges]
        )
    )
    data_term = (
        math.sqrt(max(0.0, float(np.dot(weights, costs))))
        * focal
    )
    regularity = (
        float(regularity_weight_px)
        * trajectory_regularity_penalty(
            deltas_deg,
            huber_delta_deg=regularity_huber_delta_deg,
        )
    )
    return float(data_term + regularity)


def refine_weighted_trajectory(
    prepared_edges,
    axis,
    transverse_direction,
    deltas_deg,
    weights,
    keep_ratio=0.70,
    step_schedule_deg=(0.25, 0.10, 0.05, 0.02),
    max_sweeps_per_step=2,
    min_delta_deg=0.05,
    improvement_epsilon_px=1e-9,
    regularity_weight_px=0.0,
    regularity_huber_delta_deg=1.0,
):
    """Coordinate descent with fixed edge weights and optional weak regularity."""
    deltas = np.asarray(deltas_deg, dtype=np.float64).copy()
    if (
        deltas.ndim != 1
        or not np.all(np.isfinite(deltas))
        or np.any(deltas <= 0.0)
    ):
        raise ValueError("deltas_deg must be finite and positive")

    weights = _normalize_weights(weights, len(prepared_edges))
    steps = tuple(float(step) for step in step_schedule_deg)
    if not steps or any(step <= 0.0 for step in steps):
        raise ValueError("step_schedule_deg must contain positive values")

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
    focal = float(
        np.median(
            [float(edge["focal_px"]) for edge in prepared_edges]
        )
    )

    spanning = [
        [
            edge_index
            for edge_index, edge in enumerate(prepared_edges)
            if int(edge["left_index"]) <= delta_index
            < int(edge["right_index"])
        ]
        for delta_index in range(len(deltas))
    ]

    def total_objective(candidate_deltas, candidate_weighted_sum):
        data_term = (
            math.sqrt(max(0.0, float(candidate_weighted_sum)))
            * focal
        )
        reg = (
            float(regularity_weight_px)
            * trajectory_regularity_penalty(
                candidate_deltas,
                huber_delta_deg=regularity_huber_delta_deg,
            )
        )
        return float(data_term + reg)

    current_objective = total_objective(deltas, weighted_sum)
    accepted_updates = 0
    evaluation_count = int(len(prepared_edges))

    for step in steps:
        for _ in range(max(1, int(max_sweeps_per_step))):
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
                    if candidate_value <= float(min_delta_deg):
                        continue

                    candidate = deltas.copy()
                    candidate[delta_index] = candidate_value
                    candidate_sum = weighted_sum
                    changed_costs = {}
                    for edge_index in affected:
                        edge = prepared_edges[edge_index]
                        new_cost = _edge_trimmed_mean_sampson_squared(
                            edge,
                            axis,
                            transverse_direction,
                            edge_angle_deg(
                                candidate,
                                edge["left_index"],
                                edge["right_index"],
                            ),
                            keep_ratio,
                        )
                        changed_costs[edge_index] = new_cost
                        candidate_sum += (
                            float(weights[edge_index])
                            * (
                                float(new_cost)
                                - float(costs[edge_index])
                            )
                        )
                    evaluation_count += len(affected)
                    objective = total_objective(
                        candidate,
                        candidate_sum,
                    )
                    if (
                        objective
                        < current_objective
                        - float(improvement_epsilon_px)
                        and (
                            best is None
                            or objective < best[0]
                        )
                    ):
                        best = (
                            objective,
                            candidate_value,
                            candidate_sum,
                            changed_costs,
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
        "accepted_updates": int(accepted_updates),
        "evaluation_count": int(evaluation_count),
    }


def _state(axis, transverse, deltas, objective):
    return {
        "axis": normalize_axis(axis).copy(),
        "transverse_orbit_direction":
            normalize_axis(transverse).copy(),
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


def alternating_robust_multibaseline_refinement(
    prepared_edges,
    initial_axis,
    initial_transverse_direction,
    initial_deltas_deg,
    weights,
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
    regularity_weight_px=0.0,
    regularity_huber_delta_deg=1.0,
):
    """Stable alternating refinement under fixed robust graph weights."""
    weights = _normalize_weights(weights, len(prepared_edges))
    frame = observable_geometry_frame(
        initial_axis,
        initial_transverse_direction,
    )
    axis = normalize_axis(frame[:, 2])
    transverse = normalize_axis(frame[:, 0])
    deltas = np.asarray(initial_deltas_deg, dtype=np.float64).copy()
    if (
        deltas.ndim != 1
        or not np.all(np.isfinite(deltas))
        or np.any(deltas <= 0.0)
    ):
        raise ValueError("initial_deltas_deg must be finite and positive")

    current_score = robust_graph_objective_px(
        prepared_edges,
        axis,
        transverse,
        deltas,
        weights,
        keep_ratio=keep_ratio,
        regularity_weight_px=regularity_weight_px,
        regularity_huber_delta_deg=regularity_huber_delta_deg,
    )
    current = _state(axis, transverse, deltas, current_score)
    best = _copy_state(current)
    accepted_history = [float(current_score)]
    history = []
    stale_rounds = 0
    termination_reason = "max_iterations"
    epsilon = float(objective_improvement_epsilon_px)
    geometry_indices = _select_geometry_edges(
        prepared_edges,
        geometry_pair_count,
    )

    for iteration in range(int(max_iterations)):
        previous = _copy_state(current)
        accepted_blocks = []
        rejected_blocks = []

        trajectory = refine_weighted_trajectory(
            prepared_edges,
            current["axis"],
            current["transverse_orbit_direction"],
            current["deltas_deg"],
            weights,
            keep_ratio=keep_ratio,
            step_schedule_deg=trajectory_step_schedule_deg,
            max_sweeps_per_step=trajectory_sweeps_per_step,
            regularity_weight_px=regularity_weight_px,
            regularity_huber_delta_deg=regularity_huber_delta_deg,
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
        geometry_score = robust_graph_objective_px(
            prepared_edges,
            geometry["axis"],
            geometry["transverse_orbit_direction"],
            current["deltas_deg"],
            weights,
            keep_ratio=keep_ratio,
            regularity_weight_px=regularity_weight_px,
            regularity_huber_delta_deg=regularity_huber_delta_deg,
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
        stale_rounds = (
            stale_rounds + 1
            if improvement <= epsilon
            else 0
        )

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
                "trajectory_accepted_updates":
                    int(trajectory["accepted_updates"]),
                "trajectory_evaluation_count":
                    int(trajectory["evaluation_count"]),
                "stale_rounds": int(stale_rounds),
            }
        )

        if (
            max_delta_change <= float(angle_tolerance_deg)
            and axis_change <= float(axis_tolerance_deg)
        ):
            termination_reason = "stable_state"
            break
        if stale_rounds >= max(1, int(patience)):
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
        "solver_mode": "r03b_robust_multibaseline",
    }
