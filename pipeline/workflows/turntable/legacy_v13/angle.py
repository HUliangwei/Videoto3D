"""Turntable angle estimation for a fixed camera and a single-axis rigid subject.

V1.3.4 keeps the existing known-pose COLMAP triangulation backend and free-span graph, but replaces
the generic essential-matrix rotation decomposition used by the production path. The estimator reads verified COLMAP two-view inlier correspondences, fits each pair directly to the one-axis Turntable essential model, and solves the same robust 1-D graph for positive per-frame angular increments. Legacy generic E/F decomposition remains available as a compatibility fallback when correspondence blobs are unavailable.

The only motion assumptions are:

* the camera is fixed;
* the subject is rigid;
* the subject rotates around one dominant axis;
* motion is primarily one-directional during the selected clip.

The total angular span is estimated from visual geometry and is *not* forced to
360 degrees.  A nearly complete turn is still recommended when full surface
coverage is desired.
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image

MAX_IMAGE_ID = 2147483647


def image_ids_to_pair_id(image_id1, image_id2):
    image_id1 = int(image_id1)
    image_id2 = int(image_id2)
    if image_id1 > image_id2:
        return MAX_IMAGE_ID * image_id2 + image_id1
    return MAX_IMAGE_ID * image_id1 + image_id2


def pair_id_to_image_ids(pair_id):
    pair_id = int(pair_id)
    return pair_id // MAX_IMAGE_ID, pair_id % MAX_IMAGE_ID


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



def _validate_tvec(tvec):
    values = np.asarray(tuple(float(v) for v in tvec), dtype=np.float64)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise ValueError("Turntable translation must contain three finite values.")
    if float(math.hypot(values[0], values[2])) <= 1e-9:
        raise ValueError("Turntable translation has no horizontal orbit baseline.")
    return values


def _turntable_rotation_y(angle_rad):
    angle_rad = float(angle_rad)
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array(
        [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
        dtype=np.float64,
    )


def _skew(vector):
    x, y, z = (float(v) for v in vector)
    return np.array(
        [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]],
        dtype=np.float64,
    )


def turntable_essential_matrix(angle_rad, tvec):
    """Return E=[t_rel]x R_rel for the existing constant-t Y-axis orbit model."""
    translation = _validate_tvec(tvec)
    rotation = _turntable_rotation_y(angle_rad)
    relative_translation = translation - rotation @ translation
    essential = _skew(relative_translation) @ rotation
    if float(np.linalg.norm(essential)) <= 1e-12:
        raise ValueError("Turntable essential matrix is degenerate at this angle.")
    return essential


def _simple_radial_normalized_points(points_px, camera):
    points = np.asarray(points_px, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected Nx2 image points.")
    model = camera.get("model_name")
    params = tuple(float(v) for v in camera.get("params", ()))
    if model != "SIMPLE_RADIAL" or len(params) != 4:
        raise RuntimeError(
            "Turntable constrained fitting currently expects SIMPLE_RADIAL [f,cx,cy,k]."
        )
    f, cx, cy, k = params
    if not math.isfinite(f) or f <= 0:
        raise ValueError("Invalid focal length.")
    distorted = (points - np.array([cx, cy], dtype=np.float64)) / float(f)
    undistorted = distorted.copy()
    for _ in range(8):
        radius2 = np.sum(undistorted * undistorted, axis=1, keepdims=True)
        scale = 1.0 + float(k) * radius2
        if np.any(np.abs(scale) <= 1e-8):
            raise ValueError("SIMPLE_RADIAL undistortion became singular.")
        undistorted = distorted / scale
    return np.column_stack((undistorted, np.ones(len(undistorted), dtype=np.float64)))


def _sampson_squared(essential, left_normalized, right_normalized):
    e = np.asarray(essential, dtype=np.float64).reshape(3, 3)
    x1 = np.asarray(left_normalized, dtype=np.float64)
    x2 = np.asarray(right_normalized, dtype=np.float64)
    ex1 = (e @ x1.T).T
    etx2 = (e.T @ x2.T).T
    numerator = np.sum(x2 * ex1, axis=1) ** 2
    denominator = (
        ex1[:, 0] ** 2
        + ex1[:, 1] ** 2
        + etx2[:, 0] ** 2
        + etx2[:, 1] ** 2
    )
    return numerator / np.maximum(denominator, 1e-15)


def fit_turntable_rotation_from_correspondences(
    left_points_px,
    right_points_px,
    camera,
    tvec,
    max_angle_deg=120.0,
    min_angle_deg=0.05,
):
    """Fit one signed Turntable angle using verified two-view correspondences.

    The generic essential decomposition has three rotational degrees of freedom.
    Turntable capture has only one: rotation around camera Y.  This routine
    searches that one-dimensional physical model and scores candidates by the
    median Sampson residual of COLMAP's verified inlier correspondences.
    """
    left_points = np.asarray(left_points_px, dtype=np.float64)
    right_points = np.asarray(right_points_px, dtype=np.float64)
    if left_points.shape != right_points.shape or left_points.ndim != 2 or left_points.shape[1] != 2:
        raise ValueError("Turntable pair points must be matching Nx2 arrays.")
    if len(left_points) < 8:
        raise ValueError("Turntable constrained fitting needs at least 8 correspondences.")
    max_angle_deg = float(max_angle_deg)
    min_angle_deg = float(min_angle_deg)
    if not math.isfinite(max_angle_deg) or max_angle_deg <= min_angle_deg:
        raise ValueError("max_angle_deg must exceed min_angle_deg.")

    left_normalized = _simple_radial_normalized_points(left_points, camera)
    right_normalized = _simple_radial_normalized_points(right_points, camera)
    focal_length = float(camera["params"][0])
    _validate_tvec(tvec)

    def score(degrees):
        degrees = float(degrees)
        if abs(degrees) < min_angle_deg:
            return float("inf")
        try:
            essential = turntable_essential_matrix(math.radians(degrees), tvec)
        except ValueError:
            return float("inf")
        squared = _sampson_squared(essential, left_normalized, right_normalized)
        if not len(squared):
            return float("inf")
        value = math.sqrt(max(0.0, float(np.median(squared)))) * focal_length
        return value if math.isfinite(value) else float("inf")

    def search_grid(values):
        scored = [(score(value), float(value)) for value in values]
        return min(scored, key=lambda item: item[0])

    coarse_positive = np.arange(min_angle_deg, max_angle_deg + 0.5, 0.5, dtype=np.float64)
    coarse = np.concatenate((-coarse_positive[::-1], coarse_positive))
    best_error, best_deg = search_grid(coarse)

    for half_width, step in ((0.8, 0.05), (0.10, 0.01)):
        start = max(-max_angle_deg, best_deg - half_width)
        stop = min(max_angle_deg, best_deg + half_width)
        values = np.arange(start, stop + step * 0.5, step, dtype=np.float64)
        values = values[np.abs(values) >= min_angle_deg]
        if len(values):
            best_error, best_deg = search_grid(values)

    if not math.isfinite(best_error):
        raise RuntimeError("Turntable constrained angle fitting failed.")
    return {
        "angle_rad": math.radians(abs(best_deg)),
        "signed_angle_rad": math.radians(best_deg),
        "direction_sign": 1 if best_deg >= 0 else -1,
        "median_sampson_px": float(best_error),
    }


def _keypoints_from_blob(rows, cols, blob):
    rows = int(rows or 0)
    cols = int(cols or 0)
    if rows <= 0 or cols < 2 or blob is None:
        return None
    values = np.frombuffer(blob, dtype=np.float32)
    if values.size != rows * cols:
        return None
    return values.reshape(rows, cols)[:, :2].astype(np.float64, copy=True)


def _matches_from_blob(rows, cols, blob):
    rows = int(rows or 0)
    cols = int(cols or 0)
    if rows <= 0 or cols != 2 or blob is None:
        return None
    values = np.frombuffer(blob, dtype=np.uint32)
    if values.size != rows * cols:
        return None
    return values.reshape(rows, cols).astype(np.int64, copy=True)


def _essential_from_geometry(f_blob, e_blob, k):
    essential = _blob_matrix(e_blob)
    if essential is not None:
        return essential
    fundamental = _blob_matrix(f_blob)
    if fundamental is None:
        return None
    return k.T @ fundamental @ k


def _matrix_similarity(left, right):
    left = np.asarray(left, dtype=np.float64).reshape(3, 3)
    right = np.asarray(right, dtype=np.float64).reshape(3, 3)
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return None
    value = abs(float(np.sum((left / left_norm) * (right / right_norm))))
    return max(0.0, min(1.0, value))


def infer_turntable_tvec_from_run(database_path, images, camera):
    """Mirror Turntable's SAM2-mask center estimate without changing its caller API."""
    masks_dir = Path(database_path).resolve().parent.parent / "masks"
    xs, ys = [], []
    for image in images:
        mask_path = masks_dir / (str(image["name"]) + ".png")
        if not mask_path.exists():
            continue
        try:
            with Image.open(mask_path) as mask_image:
                bbox = mask_image.convert("L").getbbox()
        except OSError:
            continue
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        xs.append((left + right) * 0.5)
        ys.append((top + bottom) * 0.5)

    f, cx, cy, _k = tuple(float(v) for v in camera["params"])
    if xs:
        u0 = float(np.median(np.asarray(xs, dtype=np.float64)))
        v0 = float(np.median(np.asarray(ys, dtype=np.float64)))
        return {
            "tvec": ((u0 - cx) / f, (v0 - cy) / f, 1.0),
            "source": "sam2_mask_median",
            "axis_px": (u0, v0),
            "mask_samples": len(xs),
        }
    return {
        "tvec": (0.0, 0.0, 1.0),
        "source": "principal_axis_fallback",
        "axis_px": (cx, cy),
        "mask_samples": 0,
    }


def _constraint_coverage(constraints, frame_count):
    gap_count = max(0, int(frame_count) - 1)
    if gap_count <= 0:
        return 0.0
    covered = np.zeros(gap_count, dtype=bool)
    for item in constraints:
        left = max(0, int(item["left"]))
        right = min(int(frame_count) - 1, int(item["right"]))
        if right > left:
            covered[left:right] = True
    return float(np.count_nonzero(covered)) / float(gap_count)


def read_turntable_constrained_constraints(
    database_path,
    images,
    camera,
    tvec,
    min_inliers=12,
    max_gap=10,
    max_pair_rotation_deg=120.0,
    max_step_rotation_deg=20.0,
    max_model_error_px=3.0,
):
    """Fit temporal COLMAP pairs to the one-axis Turntable essential model."""
    database_path = Path(database_path)
    if len(images) < 2:
        return {"constraints": [], "comparisons": []}
    by_id = {int(image["image_id"]): index for index, image in enumerate(images)}
    k_matrix = _camera_matrix(camera)
    _validate_tvec(tvec)

    connection = sqlite3.connect(str(database_path))
    try:
        keypoints = {}
        for image_id, rows, cols, data in connection.execute(
            "SELECT image_id, rows, cols, data FROM keypoints"
        ).fetchall():
            parsed = _keypoints_from_blob(rows, cols, data)
            if parsed is not None:
                keypoints[int(image_id)] = parsed
        geometry_rows = connection.execute(
            "SELECT pair_id, rows, cols, data, F, E FROM two_view_geometries WHERE rows>=?",
            (int(min_inliers),),
        ).fetchall()
    except sqlite3.OperationalError:
        return {"constraints": [], "comparisons": []}
    finally:
        connection.close()

    constraints = []
    comparisons = []
    for pair_id, inliers, match_cols, match_blob, f_blob, e_blob in geometry_rows:
        image_id1, image_id2 = pair_id_to_image_ids(pair_id)
        if image_id1 not in by_id or image_id2 not in by_id:
            continue
        index1 = by_id[image_id1]
        index2 = by_id[image_id2]
        if index1 == index2:
            continue
        left = min(index1, index2)
        right = max(index1, index2)
        gap = right - left
        if gap <= 0 or gap > int(max_gap):
            continue

        matches = _matches_from_blob(inliers, match_cols, match_blob)
        if matches is None or image_id1 not in keypoints or image_id2 not in keypoints:
            continue
        points1 = keypoints[image_id1]
        points2 = keypoints[image_id2]
        valid = (
            (matches[:, 0] >= 0)
            & (matches[:, 0] < len(points1))
            & (matches[:, 1] >= 0)
            & (matches[:, 1] < len(points2))
        )
        matches = matches[valid]
        if len(matches) < max(8, int(min_inliers)):
            continue
        canonical_left_points = points1[matches[:, 0]]
        canonical_right_points = points2[matches[:, 1]]
        reverse = index1 > index2
        if reverse:
            left_points = canonical_right_points
            right_points = canonical_left_points
        else:
            left_points = canonical_left_points
            right_points = canonical_right_points

        max_angle = min(
            float(max_pair_rotation_deg),
            float(max_step_rotation_deg) * float(gap),
        )
        if max_angle <= 0.05:
            continue
        try:
            fitted = fit_turntable_rotation_from_correspondences(
                left_points,
                right_points,
                camera,
                tvec,
                max_angle_deg=max_angle,
            )
        except Exception:
            continue

        observed_e = _essential_from_geometry(f_blob, e_blob, k_matrix)
        if observed_e is not None and reverse:
            observed_e = observed_e.T
        legacy_angle = None
        if observed_e is not None:
            try:
                legacy_angle = estimate_relative_rotation_from_essential(observed_e)
            except Exception:
                legacy_angle = None
        try:
            model_e = turntable_essential_matrix(fitted["signed_angle_rad"], tvec)
            model_similarity = _matrix_similarity(observed_e, model_e) if observed_e is not None else None
        except Exception:
            model_similarity = None

        model_error = float(fitted["median_sampson_px"])
        accepted = (
            math.isfinite(model_error)
            and model_error <= float(max_model_error_px)
            and float(fitted["angle_rad"]) >= math.radians(0.05)
        )
        rejection_reason = None if accepted else "turntable model residual above threshold"
        comparison = {
            "left": int(left),
            "right": int(right),
            "gap": int(gap),
            "inliers": int(len(matches)),
            "legacy_angle_deg": None if legacy_angle is None else math.degrees(float(legacy_angle)),
            "constrained_angle_deg": math.degrees(float(fitted["angle_rad"])),
            "direction_sign": int(fitted["direction_sign"]),
            "model_residual_px": model_error,
            "model_similarity": model_similarity,
            "accepted": bool(accepted),
            "rejection_reason": rejection_reason,
        }
        comparisons.append(comparison)
        if accepted:
            constraints.append(
                {
                    "left": int(left),
                    "right": int(right),
                    "gap": int(gap),
                    "angle_rad": float(fitted["angle_rad"]),
                    "inliers": int(len(matches)),
                    "model_error_px": model_error,
                    "direction_sign": int(fitted["direction_sign"]),
                    "legacy_angle_rad": legacy_angle,
                }
            )

    constraints.sort(key=lambda item: (item["left"], item["right"]))
    comparisons.sort(key=lambda item: (item["left"], item["right"]))
    return {"constraints": constraints, "comparisons": comparisons}


def estimate_relative_rotation_from_essential(essential):
    """Return the smaller valid rotation magnitude implied by an essential matrix."""
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


def _rotation_from_geometry(f_blob, e_blob, k):
    e = _blob_matrix(e_blob)
    if e is None:
        f = _blob_matrix(f_blob)
        if f is not None:
            e = k.T @ f @ k
    if e is None:
        return None
    try:
        angle = estimate_relative_rotation_from_essential(e)
    except Exception:
        return None
    return float(angle) if math.isfinite(angle) else None


def read_pair_rotation_constraints(
    database_path,
    images,
    camera,
    min_inliers=12,
    max_gap=10,
    max_pair_rotation_deg=120.0,
    max_step_rotation_deg=20.0,
):
    """Return verified temporal pair rotations as graph constraints.

    Each constraint is ``theta[right] - theta[left] ~= angle_rad``.  Rotation
    sign is intentionally not inferred from E: the Turntable capture contract
    supplies the one-direction motion prior, so filename order defines the
    positive direction and the existing CW/CCW triangulation stage resolves the
    virtual-camera direction later.
    """
    database_path = Path(database_path)
    if len(images) < 2:
        return []

    by_id = {int(image["image_id"]): index for index, image in enumerate(images)}
    k = _camera_matrix(camera)
    max_pair_rotation = math.radians(float(max_pair_rotation_deg))
    max_step_rotation = math.radians(float(max_step_rotation_deg))
    output = []

    connection = sqlite3.connect(str(database_path))
    try:
        rows = connection.execute(
            "SELECT pair_id, rows, F, E FROM two_view_geometries WHERE rows>=?",
            (int(min_inliers),),
        ).fetchall()
    finally:
        connection.close()

    for pair_id, inliers, f_blob, e_blob in rows:
        image_id1, image_id2 = pair_id_to_image_ids(pair_id)
        if image_id1 not in by_id or image_id2 not in by_id:
            continue
        left = by_id[image_id1]
        right = by_id[image_id2]
        if left > right:
            left, right = right, left
        gap = right - left
        if gap <= 0 or gap > int(max_gap):
            continue

        angle = _rotation_from_geometry(f_blob, e_blob, k)
        if angle is None:
            continue
        if angle <= math.radians(0.01) or angle >= max_pair_rotation:
            continue
        # Reject implausible per-frame jumps while still allowing larger total
        # rotations for verified multi-frame baselines. For example, a 36°
        # constraint over 4 gaps is valid (9°/gap), while a 36° adjacent jump is
        # treated as likely epipolar mismatch for this low-cost capture mode.
        if (angle / float(gap)) > max_step_rotation:
            continue

        output.append(
            {
                "left": int(left),
                "right": int(right),
                "gap": int(gap),
                "angle_rad": float(angle),
                "inliers": int(inliers or 0),
            }
        )

    output.sort(key=lambda item: (item["left"], item["right"]))
    return output


def read_adjacent_pair_rotations(database_path, images, camera, min_inliers=12):
    """Backward-compatible adjacent-pair reader used by diagnostics/tests."""
    constraints = read_pair_rotation_constraints(
        database_path,
        images,
        camera,
        min_inliers=min_inliers,
        max_gap=1,
        max_pair_rotation_deg=60.0,
        max_step_rotation_deg=20.0,
    )
    lookup = {(item["left"], item["right"]): item["angle_rad"] for item in constraints}
    return [lookup.get((index, index + 1)) for index in range(max(0, len(images) - 1))]


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
    """Legacy V1.3.2 helper retained for compatibility with old tools/tests.

    New reconstruction code does not call this function.  It intentionally
    preserves V1.3.2's full-turn normalization semantics for callers that
    explicitly rely on that historical behavior.
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
    filled = [global_median if value is None else float(value) for value in raw_increments]

    robust = []
    for index, value in enumerate(filled):
        local = _local_median(filled, index, radius=2)
        lower = max(math.radians(0.01), local * 0.12)
        upper = min(math.radians(60.0), local * 5.0)
        robust.append(local if value < lower or value > upper else value)

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


def _constraint_row(left, right, gap_count):
    row = np.zeros(gap_count, dtype=np.float64)
    row[int(left):int(right)] = 1.0
    return row


def solve_free_span_increments(constraints, frame_count, robust_iterations=5):
    """Solve positive per-frame increments from a multi-baseline rotation graph.

    The data terms are pair-angle equations over sums of adjacent increments.
    Weak per-gap priors make uncovered gaps solvable without inventing a 360°
    total span.  Iteratively reweighted least squares suppresses inconsistent
    pair geometry while retaining genuine non-uniform speed.
    """
    frame_count = int(frame_count)
    if frame_count < 2:
        raise ValueError("frame_count must be >= 2")
    gap_count = frame_count - 1

    usable = [
        item for item in constraints
        if 0 <= int(item["left"]) < int(item["right"]) < frame_count
        and math.isfinite(float(item["angle_rad"]))
        and float(item["angle_rad"]) > 0
    ]
    if len(usable) < 3:
        raise RuntimeError(
            "Turntable free-span estimation needs at least 3 verified temporal pairs; found {}."
            .format(len(usable))
        )

    speeds = [float(item["angle_rad"]) / float(item["right"] - item["left"]) for item in usable]
    base_speed = _median(speeds)
    if not math.isfinite(base_speed) or base_speed <= 0:
        raise RuntimeError("Could not derive a valid Turntable angular-speed prior.")

    data_a = np.vstack([
        _constraint_row(item["left"], item["right"], gap_count)
        for item in usable
    ])
    data_b = np.asarray([float(item["angle_rad"]) for item in usable], dtype=np.float64)
    inlier_strength = np.asarray(
        [math.sqrt(max(1.0, float(item.get("inliers", 1)))) for item in usable],
        dtype=np.float64,
    )
    median_strength = max(_median(inlier_strength.tolist()), 1e-9)
    data_weights = np.clip(inlier_strength / median_strength, 0.45, 2.5)
    model_quality = np.asarray(
        [
            1.0 / math.sqrt(1.0 + (float(item.get("model_error_px", 0.0)) / 1.5) ** 2)
            if item.get("model_error_px") is not None
            else 1.0
            for item in usable
        ],
        dtype=np.float64,
    )
    data_weights *= np.clip(model_quality, 0.35, 1.0)

    # Build a local speed prior from every graph edge that crosses each gap.
    # Covered gaps inherit the median visual speed. Interior graph holes are
    # linearly bridged between their nearest covered neighbours; leading/trailing
    # holes conservatively use the global median. The prior stays deliberately
    # weak so verified pair equations remain authoritative.
    gap_speed_samples = [[] for _ in range(gap_count)]
    for item in usable:
        speed = float(item["angle_rad"]) / float(item["right"] - item["left"])
        for gap_index in range(int(item["left"]), int(item["right"])):
            gap_speed_samples[gap_index].append(speed)
    local_prior = [(_median(values) if values else None) for values in gap_speed_samples]
    covered_indices = [index for index, value in enumerate(local_prior) if value is not None]
    prior_values = []
    for index, value in enumerate(local_prior):
        if value is not None:
            prior_values.append(float(value))
            continue
        left_candidates = [item for item in covered_indices if item < index]
        right_candidates = [item for item in covered_indices if item > index]
        if left_candidates and right_candidates:
            left_index = left_candidates[-1]
            right_index = right_candidates[0]
            alpha = (index - left_index) / float(right_index - left_index)
            bridged = (1.0 - alpha) * float(local_prior[left_index]) + alpha * float(local_prior[right_index])
            prior_values.append(bridged)
        else:
            prior_values.append(base_speed)

    prior_weight = 0.004
    smooth_weight = 0.0015
    prior_a = np.eye(gap_count, dtype=np.float64)
    prior_b = np.asarray(prior_values, dtype=np.float64)
    if gap_count > 1:
        smooth_a = np.zeros((gap_count - 1, gap_count), dtype=np.float64)
        for index in range(gap_count - 1):
            smooth_a[index, index] = -1.0
            smooth_a[index, index + 1] = 1.0
        smooth_b = np.zeros(gap_count - 1, dtype=np.float64)
    else:
        smooth_a = np.zeros((0, gap_count), dtype=np.float64)
        smooth_b = np.zeros(0, dtype=np.float64)

    robust = np.ones(len(usable), dtype=np.float64)
    solution = prior_b.copy()
    min_increment = math.radians(0.005)

    for _ in range(max(1, int(robust_iterations))):
        combined_a = [data_a, prior_a, smooth_a]
        combined_b = [data_b, prior_b, smooth_b]
        combined_w = [
            data_weights * robust,
            np.full(gap_count, prior_weight, dtype=np.float64),
            np.full(len(smooth_b), smooth_weight, dtype=np.float64),
        ]
        a = np.vstack(combined_a)
        b = np.concatenate(combined_b)
        w = np.concatenate(combined_w)
        root_w = np.sqrt(np.maximum(w, 1e-12))
        solution = np.linalg.lstsq(a * root_w[:, None], b * root_w, rcond=None)[0]
        solution = np.maximum(solution, min_increment)

        residual = data_a @ solution - data_b
        abs_residual = np.abs(residual)
        scale = max(_median(abs_residual.tolist()), math.radians(0.25))
        huber = max(math.radians(3.0), 4.0 * scale)
        robust = np.ones_like(abs_residual)
        mask = abs_residual > huber
        robust[mask] = huber / np.maximum(abs_residual[mask], 1e-12)

    predicted = data_a @ solution
    residual = predicted - data_b
    covered = np.zeros(gap_count, dtype=bool)
    for item in usable:
        covered[int(item["left"]):int(item["right"])] = True

    return {
        "increments_rad": [float(value) for value in solution],
        "constraint_count": len(usable),
        "gap_coverage_ratio": float(np.count_nonzero(covered)) / float(gap_count),
        "median_speed_rad": float(base_speed),
        "median_abs_residual_rad": float(_median(np.abs(residual).tolist())),
        "max_abs_residual_rad": float(np.max(np.abs(residual))) if len(residual) else 0.0,
    }


def _trajectory_confidence(adjacent_valid_ratio, gap_coverage_ratio, median_residual_rad, max_residual_rad, constraint_count, frame_count):
    reasons = []
    severity = 0  # 0=high, 1=medium, 2=low

    if gap_coverage_ratio < 0.35:
        severity = max(severity, 2)
        reasons.append("graph coverage below 35%")
    elif gap_coverage_ratio < 0.65:
        severity = max(severity, 1)
        reasons.append("graph coverage below 65%")

    if adjacent_valid_ratio < 0.30:
        severity = max(severity, 2)
        reasons.append("adjacent verified pairs below 30%")
    elif adjacent_valid_ratio < 0.55:
        severity = max(severity, 1)
        reasons.append("adjacent verified pairs below 55%")

    median_residual_deg = math.degrees(float(median_residual_rad))
    max_residual_deg = math.degrees(float(max_residual_rad))
    if median_residual_deg > 2.0 or max_residual_deg > 8.0:
        severity = max(severity, 2)
        reasons.append("rotation graph residuals are high")
    elif median_residual_deg > 1.0 or max_residual_deg > 4.0:
        severity = max(severity, 1)
        reasons.append("rotation graph residuals are elevated")

    expected_constraints = max(6, int(math.ceil(max(frame_count - 1, 1) * 0.25)))
    if constraint_count < expected_constraints:
        severity = max(severity, 1)
        reasons.append("few verified multi-frame constraints")

    confidence = ("high", "medium", "low")[severity]
    if not reasons:
        reasons.append("visual constraints provide broad, consistent coverage")
    return confidence, reasons


def cumulative_angles_from_increments(increments):
    angles = [0.0]
    total = 0.0
    for increment in increments:
        total += float(increment)
        angles.append(total)
    return angles


def estimate_adaptive_turntable_angles(
    database_path,
    images,
    camera,
    min_inliers=12,
    max_gap=10,
    max_step_rotation_deg=20.0,
    tvec=None,
    max_model_error_px=3.0,
):
    """Estimate a monotonic free-span trajectory using constrained Turntable geometry.

    V1.3.4 prefers verified keypoint correspondences fitted directly to the
    one-axis orbit essential model.  If an old/synthetic database has no usable
    inlier-match blobs, the V1.3.3 generic essential-magnitude reader remains a
    compatibility fallback rather than inventing geometry.
    """
    if tvec is None:
        center = infer_turntable_tvec_from_run(database_path, images, camera)
        tvec = center["tvec"]
        center_source = center["source"]
    else:
        tvec = tuple(float(v) for v in tvec)
        _validate_tvec(tvec)
        center_source = "caller_supplied"

    constrained_result = read_turntable_constrained_constraints(
        database_path,
        images,
        camera,
        tvec,
        min_inliers=min_inliers,
        max_gap=max_gap,
        max_step_rotation_deg=max_step_rotation_deg,
        max_model_error_px=max_model_error_px,
    )
    constrained_constraints = constrained_result["constraints"]
    legacy_constraints = read_pair_rotation_constraints(
        database_path,
        images,
        camera,
        min_inliers=min_inliers,
        max_gap=max_gap,
        max_step_rotation_deg=max_step_rotation_deg,
    )

    if len(constrained_constraints) >= 3:
        active_constraints = constrained_constraints
        angle_estimator = "turntable_constrained_essential_v134"
    else:
        active_constraints = legacy_constraints
        angle_estimator = "legacy_generic_essential_fallback"

    solved = solve_free_span_increments(active_constraints, len(images))
    increments = solved["increments_rad"]
    angles = cumulative_angles_from_increments(increments)

    active_adjacent_lookup = {
        (int(item["left"]), int(item["right"])): float(item["angle_rad"])
        for item in active_constraints
        if int(item["right"]) - int(item["left"]) == 1
    }
    adjacent = [
        active_adjacent_lookup.get((index, index + 1))
        for index in range(max(0, len(images) - 1))
    ]
    legacy_adjacent = read_adjacent_pair_rotations(
        database_path,
        images,
        camera,
        min_inliers=min_inliers,
    )

    expected_adjacent = max(len(images) - 1, 1)
    adjacent_valid = sum(value is not None for value in adjacent)
    adjacent_valid_ratio = adjacent_valid / float(expected_adjacent)
    span_rad = float(angles[-1])
    confidence, confidence_reasons = _trajectory_confidence(
        adjacent_valid_ratio,
        solved["gap_coverage_ratio"],
        solved["median_abs_residual_rad"],
        solved["max_abs_residual_rad"],
        solved["constraint_count"],
        len(images),
    )

    accepted_model_errors = [
        float(item["model_error_px"])
        for item in constrained_constraints
        if item.get("model_error_px") is not None
    ]
    median_model_error = _median(accepted_model_errors) if accepted_model_errors else None
    max_model_error = max(accepted_model_errors) if accepted_model_errors else None
    if angle_estimator == "turntable_constrained_essential_v134":
        if median_model_error is not None and median_model_error > 2.0:
            confidence = "low" if confidence == "medium" else "medium" if confidence == "high" else confidence
            confidence_reasons.append("constrained Turntable model residual is elevated")

    legacy_total_span_deg = None
    if len(legacy_constraints) >= 3:
        try:
            legacy_solved = solve_free_span_increments(legacy_constraints, len(images))
            legacy_total_span_deg = math.degrees(sum(legacy_solved["increments_rad"]))
        except Exception:
            legacy_total_span_deg = None

    constrained_coverage = _constraint_coverage(constrained_constraints, len(images))
    comparison = constrained_result["comparisons"]
    legacy_adjacent_valid = sum(value is not None for value in legacy_adjacent)

    return {
        "angles_rad": angles,
        "increments_rad": increments,
        "raw_increments_rad": adjacent,
        "valid_ratio": adjacent_valid_ratio,
        "fallback_uniform": False,
        "median_raw_rad": _median([value for value in adjacent if value is not None]) if adjacent_valid else None,
        "report": {
            "strategy": "adaptive_free_span_graph",
            "angle_estimator": angle_estimator,
            "total_span_deg": math.degrees(span_rad),
            "legacy_total_span_deg": legacy_total_span_deg,
            "forced_full_turn": False,
            "confidence": confidence,
            "confidence_reasons": confidence_reasons,
            "max_step_rotation_deg": float(max_step_rotation_deg),
            "max_model_error_px": float(max_model_error_px),
            "rotation_center_tvec": [float(v) for v in tvec],
            "rotation_center_source": center_source,
            "valid_pair_ratio": adjacent_valid_ratio,
            "valid_pairs": adjacent_valid,
            "total_pairs": len(adjacent),
            "legacy_valid_pair_ratio": legacy_adjacent_valid / float(expected_adjacent),
            "constrained_valid_pairs": len(constrained_constraints),
            "constrained_pair_coverage_ratio": constrained_coverage,
            "median_model_residual_px": median_model_error,
            "max_model_residual_px": max_model_error,
            "graph_constraints": solved["constraint_count"],
            "graph_gap_coverage_ratio": solved["gap_coverage_ratio"],
            "graph_median_abs_residual_deg": math.degrees(solved["median_abs_residual_rad"]),
            "graph_max_abs_residual_deg": math.degrees(solved["max_abs_residual_rad"]),
            "raw_increment_deg": [None if value is None else math.degrees(value) for value in adjacent],
            "legacy_raw_increment_deg": [None if value is None else math.degrees(value) for value in legacy_adjacent],
            "estimated_increment_deg": [math.degrees(value) for value in increments],
            "normalized_increment_deg": [math.degrees(value) for value in increments],
            "cumulative_angle_deg": [math.degrees(value) for value in angles],
            "pair_comparison": comparison,
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
