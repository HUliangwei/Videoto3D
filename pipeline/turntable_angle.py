"""Adaptive per-frame angle estimation for fixed-camera Turntable capture.

The estimator reuses COLMAP's verified adjacent-pair geometry from the
`two_view_geometries` SQLite table. It extracts the essential matrix (or
reconstructs it from F and K), decomposes it to a relative rotation magnitude,
robustly smooths the increments, and normalizes the cumulative motion to one
nearly-complete 360-degree virtual orbit.

This module uses only NumPy + Python stdlib and is intended for env/core.
"""

from __future__ import annotations

import json
import math
import sqlite3
import struct
from pathlib import Path

import numpy as np

MAX_IMAGE_ID = 2147483647


def image_ids_to_pair_id(image_id1, image_id2):
    image_id1 = int(image_id1)
    image_id2 = int(image_id2)
    if image_id1 > image_id2:
        return MAX_IMAGE_ID * image_id2 + image_id1
    return MAX_IMAGE_ID * image_id1 + image_id2


def _blob_matrix(blob):
    if blob is None:
        return None
    values = np.frombuffer(blob, dtype=np.float64)
    if values.size != 9:
        return None
    return values.reshape(3, 3).copy()


def _camera_matrix(camera):
    model = camera.get("model_name")
    params = tuple(float(v) for v in camera.get("params", ()))
    if model != "SIMPLE_RADIAL" or len(params) != 4:
        raise RuntimeError(
            "Adaptive Turntable currently expects SIMPLE_RADIAL intrinsics [f,cx,cy,k]."
        )
    f, cx, cy, _k = params
    return np.array(
        [
            [f, 0.0, cx],
            [0.0, f, cy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def estimate_relative_rotation_from_essential(essential):
    """Return the smaller valid rotation magnitude implied by an essential matrix.

    Essential decomposition yields two rotation candidates. For adjacent
    turntable frames, the physically plausible candidate is expected to be the
    small rotation rather than the near-180-degree alternative.
    """
    e = np.asarray(essential, dtype=np.float64).reshape(3, 3)
    if not np.all(np.isfinite(e)):
        raise ValueError("Essential matrix contains non-finite values.")
    if float(np.linalg.norm(e)) <= 1e-12:
        raise ValueError("Essential matrix is degenerate.")

    u, _s, vt = np.linalg.svd(e)
    if np.linalg.det(u) < 0:
        u[:, -1] *= -1.0
    if np.linalg.det(vt) < 0:
        vt[-1, :] *= -1.0

    w = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    angles = []
    for rotation in (u @ w @ vt, u @ w.T @ vt):
        if np.linalg.det(rotation) < 0:
            rotation = -rotation
        value = float((np.trace(rotation) - 1.0) * 0.5)
        value = max(-1.0, min(1.0, value))
        angles.append(math.acos(value))
    return min(angles)


def read_adjacent_pair_rotations(database_path, images, camera, min_inliers=12):
    """Read verified adjacent-pair geometry and return one raw angle per gap.

    Result length is `len(images)-1`. Missing/invalid pairs are represented by
    None. F is converted to E using K when E is unavailable.
    """
    database_path = Path(database_path)
    if len(images) < 2:
        return []

    k = _camera_matrix(camera)
    connection = sqlite3.connect(str(database_path))
    try:
        output = []
        for left, right in zip(images[:-1], images[1:]):
            pair_id = image_ids_to_pair_id(left["image_id"], right["image_id"])
            row = connection.execute(
                "SELECT rows, F, E FROM two_view_geometries WHERE pair_id=?",
                (pair_id,),
            ).fetchone()
            if row is None:
                output.append(None)
                continue

            rows, f_blob, e_blob = row
            if int(rows or 0) < int(min_inliers):
                output.append(None)
                continue

            e = _blob_matrix(e_blob)
            if e is None:
                f = _blob_matrix(f_blob)
                if f is not None:
                    e = k.T @ f @ k

            if e is None:
                output.append(None)
                continue

            try:
                angle = estimate_relative_rotation_from_essential(e)
            except Exception:
                output.append(None)
                continue

            # Adjacent full-turn video should not jump close to 180 degrees.
            if not math.isfinite(angle) or angle <= math.radians(0.01) or angle >= math.radians(60.0):
                output.append(None)
                continue
            output.append(float(angle))
        return output
    finally:
        connection.close()


def _median(values):
    arr = sorted(float(v) for v in values)
    count = len(arr)
    if not count:
        raise ValueError("median of empty sequence")
    middle = count // 2
    if count % 2:
        return arr[middle]
    return 0.5 * (arr[middle - 1] + arr[middle])


def _local_median(values, index, radius=2):
    start = max(0, index - radius)
    stop = min(len(values), index + radius + 1)
    return _median(values[start:stop])


def smooth_and_normalize_increments(raw_increments, frame_count):
    """Fill, robustly smooth, and normalize angle increments to one full-turn span.

    The target span matches the prior uniform implementation:
    `2π * (N-1)/N`, which avoids making first and last registered poses exactly
    coincident.
    """
    if frame_count < 2:
        raise ValueError("frame_count must be >= 2")
    expected_gaps = frame_count - 1
    if len(raw_increments) != expected_gaps:
        raise ValueError(
            "Expected {} increments for {} frames, got {}.".format(
                expected_gaps, frame_count, len(raw_increments)
            )
        )

    valid = [
        float(v)
        for v in raw_increments
        if v is not None and math.isfinite(float(v)) and float(v) > 0
    ]
    valid_ratio = len(valid) / float(expected_gaps)
    enough_visual_geometry = len(valid) >= max(3, int(math.ceil(expected_gaps * 0.30)))

    if not enough_visual_geometry:
        uniform = 2.0 * math.pi / float(frame_count)
        normalized = [uniform] * expected_gaps
        return {
            "increments_rad": normalized,
            "valid_ratio": valid_ratio,
            "fallback_uniform": True,
            "median_raw_rad": _median(valid) if valid else None,
        }

    global_median = _median(valid)
    filled = [
        global_median if value is None else float(value)
        for value in raw_increments
    ]

    # Hampel-like local outlier replacement. Keep genuine speed variation, but
    # suppress isolated epipolar failures that imply implausible jumps.
    robust = []
    for index, value in enumerate(filled):
        local = _local_median(filled, index, radius=2)
        lower = max(math.radians(0.01), local * 0.12)
        upper = min(math.radians(60.0), local * 5.0)
        if value < lower or value > upper:
            robust.append(local)
        else:
            robust.append(value)

    # Light smoothing: retain most measured speed variation.
    smoothed = []
    for index, value in enumerate(robust):
        local = _local_median(robust, index, radius=1)
        smoothed.append(0.80 * value + 0.20 * local)

    total = sum(smoothed)
    if not math.isfinite(total) or total <= 1e-12:
        raise RuntimeError("Adaptive Turntable angle normalization failed.")

    target_span = 2.0 * math.pi * (frame_count - 1) / float(frame_count)
    scale = target_span / total
    normalized = [max(1e-8, value * scale) for value in smoothed]

    return {
        "increments_rad": normalized,
        "valid_ratio": valid_ratio,
        "fallback_uniform": False,
        "median_raw_rad": global_median,
    }


def cumulative_angles_from_increments(increments):
    angles = [0.0]
    total = 0.0
    for increment in increments:
        total += float(increment)
        angles.append(total)
    return angles


def estimate_adaptive_turntable_angles(database_path, images, camera, min_inliers=12):
    raw = read_adjacent_pair_rotations(
        database_path,
        images,
        camera,
        min_inliers=min_inliers,
    )
    normalized = smooth_and_normalize_increments(raw, len(images))
    angles = cumulative_angles_from_increments(normalized["increments_rad"])

    raw_deg = [None if value is None else math.degrees(value) for value in raw]
    inc_deg = [math.degrees(value) for value in normalized["increments_rad"]]
    angles_deg = [math.degrees(value) for value in angles]

    return {
        "angles_rad": angles,
        "increments_rad": normalized["increments_rad"],
        "raw_increments_rad": raw,
        "valid_ratio": normalized["valid_ratio"],
        "fallback_uniform": normalized["fallback_uniform"],
        "median_raw_rad": normalized["median_raw_rad"],
        "report": {
            "strategy": (
                "uniform_360_fallback"
                if normalized["fallback_uniform"]
                else "adaptive_360_epipolar"
            ),
            "valid_pair_ratio": normalized["valid_ratio"],
            "valid_pairs": sum(value is not None for value in raw),
            "total_pairs": len(raw),
            "raw_increment_deg": raw_deg,
            "normalized_increment_deg": inc_deg,
            "cumulative_angle_deg": angles_deg,
        },
    }


def write_angle_report(path, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result["report"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
