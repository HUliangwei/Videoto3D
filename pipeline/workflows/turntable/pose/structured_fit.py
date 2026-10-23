"""Structured essential angle estimator for Turntable R0.2a."""
from __future__ import annotations
import math
import numpy as np
from .single_axis import structured_essential_matrix

def _points2(values, name):
    points = np.asarray(values, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("{} must be Nx2".format(name))
    if len(points) < 8 or not np.all(np.isfinite(points)):
        raise ValueError("{} must contain at least 8 finite points".format(name))
    return points

def _intrinsics(matrix):
    k = np.asarray(matrix, dtype=np.float64)
    if k.shape != (3, 3) or not np.all(np.isfinite(k)):
        raise ValueError("intrinsics must be a finite 3x3 matrix")
    if abs(float(np.linalg.det(k))) <= 1e-12:
        raise ValueError("intrinsics matrix is singular")
    return k

def normalized_homogeneous(points_px, intrinsics):
    points = _points2(points_px, "points_px")
    k = _intrinsics(intrinsics)
    homogeneous = np.column_stack((points, np.ones(len(points), dtype=np.float64)))
    normalized = np.linalg.solve(k, homogeneous.T).T
    return normalized / normalized[:, 2:3]

def sampson_squared(essential, left_h, right_h):
    e = np.asarray(essential, dtype=np.float64).reshape(3, 3)
    left = np.asarray(left_h, dtype=np.float64)
    right = np.asarray(right_h, dtype=np.float64)
    ex1 = (e @ left.T).T
    etx2 = (e.T @ right.T).T
    numerator = np.sum(right * ex1, axis=1) ** 2
    denominator = ex1[:,0]**2 + ex1[:,1]**2 + etx2[:,0]**2 + etx2[:,1]**2
    return numerator / np.maximum(denominator, 1e-15)

def structured_angle_residual_px(left_points_px, right_points_px, intrinsics, axis, orbit_vector, signed_angle_deg):
    left = _points2(left_points_px, "left_points_px")
    right = _points2(right_points_px, "right_points_px")
    if left.shape != right.shape:
        raise ValueError("left/right correspondence arrays must match")
    k = _intrinsics(intrinsics)
    e = structured_essential_matrix(axis, orbit_vector, math.radians(float(signed_angle_deg)))
    squared = sampson_squared(e, normalized_homogeneous(left, k), normalized_homogeneous(right, k))
    focal_px = 0.5 * (abs(float(k[0,0])) + abs(float(k[1,1])))
    return math.sqrt(max(0.0, float(np.median(squared)))) * focal_px

def fit_structured_angle(left_points_px, right_points_px, intrinsics, axis, orbit_vector,
                         max_abs_angle_deg=120.0, min_abs_angle_deg=0.05, coarse_step_deg=0.25):
    left = _points2(left_points_px, "left_points_px")
    right = _points2(right_points_px, "right_points_px")
    if left.shape != right.shape:
        raise ValueError("left/right correspondence arrays must match")
    max_abs_angle_deg = float(max_abs_angle_deg)
    min_abs_angle_deg = float(min_abs_angle_deg)
    coarse_step_deg = float(coarse_step_deg)
    if max_abs_angle_deg <= min_abs_angle_deg or min_abs_angle_deg <= 0 or coarse_step_deg <= 0:
        raise ValueError("invalid angle search range")

    def score(deg):
        if abs(float(deg)) < min_abs_angle_deg:
            return float("inf")
        try:
            return structured_angle_residual_px(left, right, intrinsics, axis, orbit_vector, float(deg))
        except ValueError:
            return float("inf")

    positive = np.arange(min_abs_angle_deg, max_abs_angle_deg + 0.5*coarse_step_deg,
                         coarse_step_deg, dtype=np.float64)
    values = np.concatenate((-positive[::-1], positive))
    best_error, best_deg = min([(score(v), float(v)) for v in values], key=lambda item: item[0])

    for half_width, step in ((0.60, 0.05), (0.10, 0.01)):
        lo = max(-max_abs_angle_deg, best_deg-half_width)
        hi = min(max_abs_angle_deg, best_deg+half_width)
        values = np.arange(lo, hi + 0.5*step, step, dtype=np.float64)
        values = values[np.abs(values) >= min_abs_angle_deg]
        best_error, best_deg = min([(score(v), float(v)) for v in values], key=lambda item: item[0])

    if not math.isfinite(best_error):
        raise RuntimeError("Structured Turntable angle fitting failed")
    return {
        "signed_angle_deg": float(best_deg),
        "signed_angle_rad": math.radians(float(best_deg)),
        "median_sampson_px": float(best_error),
        "correspondence_count": int(len(left)),
        "shared_geometry_fixed": True,
    }
