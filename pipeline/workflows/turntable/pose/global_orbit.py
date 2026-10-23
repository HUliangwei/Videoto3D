"""Robust global turntable orbit solve for the engineering-first R0.4 route."""
from __future__ import annotations

import math
import numpy as np


def measurements_from_r03c(report, include_gap5=True):
    """Convert R0.3c top-1 pair hypotheses into a gated measurement set.

    Gaps 2/3 are primary constraints. Gap 5 is accepted only when its
    pair Sampson residual is compatible with the short-baseline distribution.
    """
    hypotheses = list(report.get("hypotheses", []))
    short_residuals = []
    for item in hypotheses:
        gap = int(item["gap"])
        candidates = item.get("candidates") or []
        if gap in (2, 3) and candidates:
            short_residuals.append(float(candidates[0]["residual_px"]))

    if not short_residuals:
        raise ValueError("R0.3c report contains no usable gap-2/3 hypotheses")

    short_median = float(np.median(short_residuals))
    gap5_threshold = max(0.5, 4.0 * short_median)

    accepted = []
    rejected = []
    for item in hypotheses:
        gap = int(item["gap"])
        if gap not in (2, 3, 5):
            continue
        if gap == 5 and not include_gap5:
            continue
        candidates = item.get("candidates") or []
        if not candidates:
            continue

        best = candidates[0]
        residual = float(best["residual_px"])
        record = {
            "left_index": int(item["left_index"]),
            "right_index": int(item["right_index"]),
            "gap": gap,
            "angle_deg": float(best["angle_deg"]),
            "residual_px": residual,
            "candidate_confidence": float(best.get("confidence", 1.0)),
        }

        if gap == 5 and residual > gap5_threshold:
            rejected.append({
                **record,
                "reason": "gap5_residual_outlier",
                "threshold_px": float(gap5_threshold),
            })
            continue

        accepted.append(record)

    return {
        "measurements": accepted,
        "rejected": rejected,
        "gap5_residual_threshold_px": float(gap5_threshold),
        "short_residual_median_px": float(short_median),
    }


def _design_row(frame_count, left_index, right_index):
    row = np.zeros(int(frame_count) - 1, dtype=np.float64)
    left = int(left_index)
    right = int(right_index)
    if not (0 <= left < right < int(frame_count)):
        raise ValueError("measurement indices outside frame_count")
    row[left:right] = 1.0
    return row


def _base_measurement_weight(record):
    residual = max(0.03, float(record.get("residual_px", 0.1)))
    confidence = max(
        0.05,
        min(1.0, float(record.get("candidate_confidence", 1.0))),
    )
    # Avoid letting tiny residuals dominate the graph.
    return confidence / residual


def _huber_weight(residual_deg, delta_deg):
    magnitude = abs(float(residual_deg))
    delta = float(delta_deg)
    if magnitude <= delta:
        return 1.0
    return delta / max(magnitude, 1e-12)


def solve_global_orbit(
    frame_count,
    measurements,
    irls_iterations=8,
    huber_delta_deg=0.35,
    min_delta_deg=0.05,
):
    """Solve adjacent positive increments from multi-baseline relative angles.

    No total-span prior or 360-degree normalization is used.
    """
    frame_count = int(frame_count)
    if frame_count < 3:
        raise ValueError("frame_count must be >= 3")
    measurements = list(measurements)
    if len(measurements) < frame_count - 2:
        raise ValueError("too few relative-angle measurements")

    design = np.stack(
        [
            _design_row(
                frame_count,
                record["left_index"],
                record["right_index"],
            )
            for record in measurements
        ],
        axis=0,
    )
    observed = np.asarray(
        [float(record["angle_deg"]) for record in measurements],
        dtype=np.float64,
    )
    base = np.asarray(
        [_base_measurement_weight(record) for record in measurements],
        dtype=np.float64,
    )

    robust = np.ones(len(measurements), dtype=np.float64)
    deltas = np.full(frame_count - 1, 1.0, dtype=np.float64)

    for _ in range(max(1, int(irls_iterations))):
        weights = np.sqrt(np.maximum(1e-12, base * robust))
        lhs = design * weights[:, None]
        rhs = observed * weights
        candidate, _, _, _ = np.linalg.lstsq(lhs, rhs, rcond=None)
        candidate = np.maximum(float(min_delta_deg), candidate)

        # One projected coordinate sweep reduces the weighted data term after
        # positivity clipping without introducing a span prior.
        prediction = design @ candidate
        error = prediction - observed
        for index in range(len(candidate)):
            column = design[:, index]
            active = column > 0.0
            if not np.any(active):
                continue
            w = base[active] * robust[active]
            denom = float(np.sum(w))
            if denom <= 1e-12:
                continue
            # Correct the subset residual in the least-squares direction.
            correction = -float(np.sum(w * error[active])) / denom
            proposed = max(float(min_delta_deg), float(candidate[index] + correction))
            if proposed != candidate[index]:
                candidate[index] = proposed
                prediction = design @ candidate
                error = prediction - observed

        residuals = design @ candidate - observed
        robust = np.asarray(
            [_huber_weight(value, huber_delta_deg) for value in residuals],
            dtype=np.float64,
        )
        deltas = candidate

    angles = np.concatenate(
        (np.asarray([0.0], dtype=np.float64), np.cumsum(deltas))
    )
    residuals = design @ deltas - observed
    monotonicity_violations = int(np.sum(np.diff(angles) <= 0.0))

    by_gap = {}
    for record, residual in zip(measurements, residuals):
        by_gap.setdefault(int(record["gap"]), []).append(abs(float(residual)))

    return {
        "deltas_deg": [float(v) for v in deltas],
        "angles_deg": [float(v) for v in angles],
        "span_deg": float(angles[-1] - angles[0]),
        "monotonicity_violations": monotonicity_violations,
        "measurement_count": int(len(measurements)),
        "residual_mae_deg": float(np.mean(np.abs(residuals))),
        "residual_max_deg": float(np.max(np.abs(residuals))),
        "per_gap_residual_mae_deg": {
            str(gap): float(np.mean(values))
            for gap, values in sorted(by_gap.items())
        },
        "forced_360_degree_span": False,
        "ground_truth_span_used": False,
        "solver": "weighted_huber_irls_positive_free_span",
        "irls_iterations": int(max(1, int(irls_iterations))),
        "huber_delta_deg": float(huber_delta_deg),
        "min_delta_deg": float(min_delta_deg),
    }
