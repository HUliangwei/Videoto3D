"""Quantitative metrics for Turntable angle/axis research."""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np

_EPS = 1e-12

def _array1(values: Iterable[float], name: str) -> np.ndarray:
    array = np.asarray(tuple(float(v) for v in values), dtype=np.float64)
    if array.ndim != 1 or len(array) < 2 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 1-D sequence with >=2 values.")
    return array

def _axis(values: Iterable[float], name: str) -> np.ndarray:
    vector = np.asarray(tuple(float(v) for v in values), dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain three finite values.")
    norm = float(np.linalg.norm(vector))
    if norm <= _EPS:
        raise ValueError(f"{name} must be non-zero.")
    return vector / norm

def axis_error_deg(estimated_axis: Iterable[float], ground_truth_axis: Iterable[float]) -> float:
    estimated = _axis(estimated_axis, "estimated_axis")
    ground_truth = _axis(ground_truth_axis, "ground_truth_axis")
    cosine = float(np.clip(abs(np.dot(estimated, ground_truth)), 0.0, 1.0))
    return math.degrees(math.acos(cosine))

def _align_angle_sequence(predicted_deg, ground_truth_deg):
    predicted = _array1(predicted_deg, "predicted_deg")
    ground_truth = _array1(ground_truth_deg, "ground_truth_deg")
    if predicted.shape != ground_truth.shape:
        raise ValueError("Predicted and ground-truth angle sequences must match.")
    candidates = []
    for sign in (1, -1):
        aligned = sign * predicted
        aligned = aligned + (ground_truth[0] - aligned[0])
        mae = float(np.mean(np.abs(aligned - ground_truth)))
        candidates.append((mae, sign, aligned))
    return min(candidates, key=lambda item: item[0])

def angle_sequence_metrics(predicted_deg, ground_truth_deg) -> dict:
    mae, sign, aligned = _align_angle_sequence(predicted_deg, ground_truth_deg)
    ground_truth = _array1(ground_truth_deg, "ground_truth_deg")
    pred_inc = np.diff(aligned)
    gt_inc = np.diff(ground_truth)
    return {
        "orientation_sign": int(sign),
        "angle_mae_deg": float(mae),
        "increment_mae_deg": float(np.mean(np.abs(pred_inc - gt_inc))),
        "span_error_deg": float(abs((aligned[-1] - aligned[0]) - (ground_truth[-1] - ground_truth[0]))),
        "monotonicity_violations": int(np.count_nonzero(pred_inc < -1e-9)),
        "aligned_angles_deg": [float(v) for v in aligned],
    }
