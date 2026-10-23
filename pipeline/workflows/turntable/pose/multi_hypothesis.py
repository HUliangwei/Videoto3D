"""Anchor-independent structured pair-angle hypotheses for Turntable R0.3c."""
from __future__ import annotations

import math
import numpy as np

from .multibaseline import _edge_trimmed_mean_sampson_squared


def _residual_px(edge, axis, transverse_direction, angle_deg, keep_ratio):
    mean_sq = _edge_trimmed_mean_sampson_squared(
        edge,
        axis,
        transverse_direction,
        float(angle_deg),
        keep_ratio,
    )
    return math.sqrt(max(0.0, float(mean_sq))) * float(edge["focal_px"])


def _angle_grid(min_angle_deg, max_angle_deg, step_deg):
    low = float(min_angle_deg)
    high = float(max_angle_deg)
    step = float(step_deg)
    if not (0.0 < low < high < 180.0):
        raise ValueError("require 0 < min_angle < max_angle < 180")
    if step <= 0.0:
        raise ValueError("step_deg must be positive")
    return np.arange(low, high + 0.5 * step, step, dtype=np.float64)


def _local_minimum_indices(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("values must be non-empty 1-D")
    if len(values) == 1:
        return [0]
    result = []
    for index in range(len(values)):
        left_ok = index == 0 or values[index] <= values[index - 1]
        right_ok = index == len(values) - 1 or values[index] <= values[index + 1]
        if left_ok and right_ok:
            result.append(index)
    global_min = int(np.argmin(values))
    if global_min not in result:
        result.append(global_min)
    return sorted(set(result))


def generate_pair_hypotheses(
    edge,
    axis,
    transverse_direction,
    min_angle_deg=0.25,
    max_angle_deg=60.0,
    coarse_step_deg=0.5,
    refine_step_deg=0.05,
    top_k=3,
    min_separation_deg=0.5,
    keep_ratio=0.70,
):
    """Search a fixed broad angle domain; no global trajectory angle is consumed."""
    top_k = max(1, int(top_k))
    min_separation_deg = float(min_separation_deg)
    if min_separation_deg <= 0.0:
        raise ValueError("min_separation_deg must be positive")
    if float(refine_step_deg) <= 0.0:
        raise ValueError("refine_step_deg must be positive")

    coarse_angles = _angle_grid(
        min_angle_deg,
        max_angle_deg,
        coarse_step_deg,
    )
    coarse_residuals = np.asarray(
        [
            _residual_px(
                edge,
                axis,
                transverse_direction,
                float(angle),
                keep_ratio,
            )
            for angle in coarse_angles
        ],
        dtype=np.float64,
    )

    minima = _local_minimum_indices(coarse_residuals)
    ranked = sorted(minima, key=lambda idx: float(coarse_residuals[idx]))

    refined = []
    evaluations = int(len(coarse_angles))
    candidate_seed_count = min(len(ranked), max(top_k * 4, top_k))

    for index in ranked[:candidate_seed_count]:
        center = float(coarse_angles[index])
        low = max(float(min_angle_deg), center - float(coarse_step_deg))
        high = min(float(max_angle_deg), center + float(coarse_step_deg))
        fine_angles = _angle_grid(low, high, refine_step_deg)
        fine_residuals = np.asarray(
            [
                _residual_px(
                    edge,
                    axis,
                    transverse_direction,
                    float(angle),
                    keep_ratio,
                )
                for angle in fine_angles
            ],
            dtype=np.float64,
        )
        evaluations += int(len(fine_angles))
        best_index = int(np.argmin(fine_residuals))
        refined.append(
            {
                "angle_deg": float(fine_angles[best_index]),
                "residual_px": float(fine_residuals[best_index]),
            }
        )

    # De-duplicate refined minima by angle separation, keeping the lower residual.
    refined.sort(key=lambda item: item["residual_px"])
    selected = []
    for candidate in refined:
        if all(
            abs(candidate["angle_deg"] - existing["angle_deg"])
            >= min_separation_deg - 1e-12
            for existing in selected
        ):
            selected.append(candidate)
        if len(selected) >= top_k:
            break

    if not selected:
        best_index = int(np.argmin(coarse_residuals))
        selected = [{
            "angle_deg": float(coarse_angles[best_index]),
            "residual_px": float(coarse_residuals[best_index]),
        }]

    best_residual = float(selected[0]["residual_px"])
    confidence_scale = max(best_residual, 0.05)
    for rank, candidate in enumerate(selected, start=1):
        candidate["rank"] = int(rank)
        candidate["confidence"] = float(
            math.exp(
                -max(0.0, candidate["residual_px"] - best_residual)
                / confidence_scale
            )
        )

    return {
        "left_index": int(edge["left_index"]),
        "right_index": int(edge["right_index"]),
        "gap": int(edge["gap"]),
        "raw_match_count": int(edge.get("raw_match_count", edge["count"])),
        "candidate_count": int(len(selected)),
        "candidates": selected,
        "search": {
            "min_angle_deg": float(min_angle_deg),
            "max_angle_deg": float(max_angle_deg),
            "coarse_step_deg": float(coarse_step_deg),
            "refine_step_deg": float(refine_step_deg),
            "top_k": int(top_k),
            "min_separation_deg": float(min_separation_deg),
            "keep_ratio": float(keep_ratio),
            "evaluation_count": int(evaluations),
        },
    }
