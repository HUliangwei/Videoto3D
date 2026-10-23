"""GT-free initialization for Turntable R0.2b-2.

The initializer uses a generic essential-matrix pose estimate independently
on each adjacent masked-image pair. It does not use the Turntable GT axis,
GT orbit, GT angles, GT span, or a forced 360-degree assumption.

Per-pair generic pose hypotheses are filtered to the physically plausible
adjacent-angle range. Valid Rodrigues axes and the orbit-direction
candidates derived from (I - R)u proportional to t are aggregated as
weighted unoriented 3-D lines.
"""

from __future__ import annotations

import math
import numpy as np

from .single_axis import normalize_axis


def rotation_angle_deg(rotation):
    rotation = np.asarray(rotation, dtype=np.float64)
    if rotation.shape != (3, 3) or not np.all(np.isfinite(rotation)):
        raise ValueError("rotation must be a finite 3x3 matrix")
    cosine = float(
        np.clip(
            (float(np.trace(rotation)) - 1.0) * 0.5,
            -1.0,
            1.0,
        )
    )
    return math.degrees(math.acos(cosine))


def _canonical_line(vector):
    vector = normalize_axis(vector)
    for value in vector:
        if abs(float(value)) > 1e-12:
            return -vector if value < 0.0 else vector
    return vector


def weighted_line_direction(vectors, weights):
    vectors = [
        normalize_axis(vector)
        for vector in vectors
    ]
    weights = [
        float(weight)
        for weight in weights
    ]
    if not vectors or len(vectors) != len(weights):
        raise ValueError("vectors/weights must be non-empty and aligned")
    if not all(
        math.isfinite(weight) and weight > 0.0
        for weight in weights
    ):
        raise ValueError("weights must be finite and positive")

    scatter = np.zeros((3, 3), dtype=np.float64)
    for vector, weight in zip(vectors, weights):
        scatter += weight * np.outer(vector, vector)

    values, eigenvectors = np.linalg.eigh(scatter)
    direction = eigenvectors[:, int(np.argmax(values))]
    return _canonical_line(direction)


def _orthogonalized_line(vector, axis):
    axis = normalize_axis(axis)
    vector = np.asarray(vector, dtype=np.float64)
    projected = vector - axis * float(np.dot(axis, vector))
    norm = float(np.linalg.norm(projected))
    if norm <= 1e-12:
        raise ValueError("line candidate is parallel to axis")
    return projected / norm


def aggregate_pose_hypotheses(
    hypotheses,
    pair_count,
    min_valid_pairs=3,
    fallback_delta_deg=5.0,
):
    """Aggregate accepted generic-pose hypotheses into one shared frame.

    Each accepted hypothesis is a dict with:
        pair_index, angle_deg, axis, transverse_candidate, weight,
        pose_inliers.
    """
    pair_count = int(pair_count)
    if pair_count < 3:
        raise ValueError("pair_count must be >= 3")

    accepted = [
        item
        for item in hypotheses
        if item.get("accepted")
    ]
    if len(accepted) < int(min_valid_pairs):
        raise RuntimeError(
            "Too few valid generic essential pose hypotheses: {}"
            .format(len(accepted))
        )

    axes = [
        np.asarray(item["axis"], dtype=np.float64)
        for item in accepted
    ]
    weights = [
        float(item["weight"])
        for item in accepted
    ]
    axis = weighted_line_direction(axes, weights)

    signed_axis_sum = np.zeros(3, dtype=np.float64)
    for vector, weight in zip(axes, weights):
        signed_axis_sum += weight * normalize_axis(vector)
    if float(np.linalg.norm(signed_axis_sum)) > 1e-12:
        if float(np.dot(axis, signed_axis_sum)) < 0.0:
            axis = -axis

    transverse_candidates = []
    transverse_weights = []
    for item, weight in zip(accepted, weights):
        try:
            candidate = _orthogonalized_line(
                item["transverse_candidate"],
                axis,
            )
        except ValueError:
            continue
        transverse_candidates.append(candidate)
        transverse_weights.append(weight)

    if len(transverse_candidates) < int(min_valid_pairs):
        raise RuntimeError(
            "Too few valid transverse-orbit candidates: {}"
            .format(len(transverse_candidates))
        )

    transverse = weighted_line_direction(
        transverse_candidates,
        transverse_weights,
    )
    transverse = _orthogonalized_line(transverse, axis)
    transverse = _canonical_line(transverse)

    valid_angles = np.asarray(
        [float(item["angle_deg"]) for item in accepted],
        dtype=np.float64,
    )
    fallback = float(np.median(valid_angles))
    if not math.isfinite(fallback) or fallback <= 0.0:
        fallback = float(fallback_delta_deg)

    per_pair = {
        int(item["pair_index"]): item
        for item in accepted
    }
    deltas = []
    initialization_records = []
    for pair_index in range(pair_count):
        item = per_pair.get(pair_index)
        if item is None:
            deltas.append(fallback)
            initialization_records.append(
                {
                    "pair_index": pair_index,
                    "accepted": False,
                    "initial_delta_deg": fallback,
                    "fallback": True,
                }
            )
        else:
            angle = float(item["angle_deg"])
            deltas.append(angle)
            initialization_records.append(
                {
                    "pair_index": pair_index,
                    "accepted": True,
                    "initial_delta_deg": angle,
                    "pose_inliers": int(item["pose_inliers"]),
                    "weight": float(item["weight"]),
                    "fallback": False,
                }
            )

    return {
        "axis": normalize_axis(axis),
        "transverse_orbit_direction": normalize_axis(transverse),
        "initial_deltas_deg": np.asarray(
            deltas,
            dtype=np.float64,
        ),
        "valid_pair_count": int(len(accepted)),
        "fallback_pair_count": int(pair_count - len(accepted)),
        "fallback_delta_deg": float(fallback),
        "records": initialization_records,
    }


def _essential_candidates(essential):
    essential = np.asarray(essential, dtype=np.float64)
    if essential.shape == (3, 3):
        return [essential]
    if (
        essential.ndim == 2
        and essential.shape[1] == 3
        and essential.shape[0] % 3 == 0
    ):
        return [
            essential[index:index + 3]
            for index in range(0, essential.shape[0], 3)
        ]
    return []


def _generic_pair_hypothesis(
    left_points_px,
    right_points_px,
    intrinsics,
    pair_index,
    min_angle_deg,
    max_angle_deg,
    ransac_threshold_px,
):
    # Deliberately lazy: outer development/test Python need not own cv2.
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "R0.2b-2 generic Essential initialization requires "
            "OpenCV in env/core"
        ) from exc

    left = np.asarray(left_points_px, dtype=np.float64)
    right = np.asarray(right_points_px, dtype=np.float64)
    k = np.asarray(intrinsics, dtype=np.float64)
    if (
        left.ndim != 2
        or left.shape[1] != 2
        or left.shape != right.shape
        or len(left) < 8
    ):
        raise ValueError("generic Essential pair requires matching Nx2")

    essential, mask = cv2.findEssentialMat(
        left,
        right,
        k,
        method=cv2.RANSAC,
        prob=0.999,
        threshold=float(ransac_threshold_px),
    )
    if essential is None:
        return None

    best = None
    for candidate in _essential_candidates(essential):
        try:
            pose_mask = None if mask is None else mask.copy()
            inliers, rotation, translation, _ = cv2.recoverPose(
                candidate,
                left,
                right,
                k,
                mask=pose_mask,
            )
        except cv2.error:
            continue

        if int(inliers) <= 0:
            continue

        angle_deg = rotation_angle_deg(rotation)
        if not (
            float(min_angle_deg)
            <= angle_deg
            <= float(max_angle_deg)
        ):
            continue

        rotation_vector, _ = cv2.Rodrigues(rotation)
        rotation_vector = rotation_vector.reshape(3)
        if float(np.linalg.norm(rotation_vector)) <= 1e-12:
            continue
        axis = normalize_axis(rotation_vector)

        translation = np.asarray(
            translation,
            dtype=np.float64,
        ).reshape(3)
        transverse_candidate = (
            np.linalg.pinv(np.eye(3) - rotation)
            @ translation
        )
        transverse_candidate = (
            transverse_candidate
            - axis
            * float(np.dot(axis, transverse_candidate))
        )
        if float(np.linalg.norm(transverse_candidate)) <= 1e-12:
            continue
        transverse_candidate = normalize_axis(
            transverse_candidate
        )

        angular_weight = math.sin(
            math.radians(angle_deg)
        ) ** 2
        weight = max(int(inliers), 1) * max(
            angular_weight,
            1e-6,
        )

        hypothesis = {
            "pair_index": int(pair_index),
            "accepted": True,
            "angle_deg": float(angle_deg),
            "axis": axis,
            "transverse_candidate": transverse_candidate,
            "pose_inliers": int(inliers),
            "weight": float(weight),
        }
        if (
            best is None
            or hypothesis["weight"] > best["weight"]
        ):
            best = hypothesis

    return best


def initialize_from_generic_essential(
    pair_observations,
    intrinsics,
    min_angle_deg=0.25,
    max_angle_deg=20.0,
    ransac_threshold_px=1.0,
    min_valid_pairs=3,
    fallback_delta_deg=5.0,
):
    """Build a GT-free free-span initializer from adjacent image pairs."""
    if len(pair_observations) < 3:
        raise ValueError("at least 3 pair observations are required")

    hypotheses = []
    rejected = []
    for pair_index, pair in enumerate(pair_observations):
        hypothesis = _generic_pair_hypothesis(
            pair["left_points_px"],
            pair["right_points_px"],
            intrinsics,
            pair_index,
            min_angle_deg,
            max_angle_deg,
            ransac_threshold_px,
        )
        if hypothesis is None:
            rejected.append(pair_index)
        else:
            hypotheses.append(hypothesis)

    result = aggregate_pose_hypotheses(
        hypotheses,
        pair_count=len(pair_observations),
        min_valid_pairs=min_valid_pairs,
        fallback_delta_deg=fallback_delta_deg,
    )
    result["rejected_pair_indices"] = [
        int(index)
        for index in rejected
    ]
    result["method"] = "generic_essential_ransac"
    result["forced_360_degree_span"] = False
    result["ground_truth_angles_used"] = False
    result["ground_truth_axis_used"] = False
    result["ground_truth_orbit_used"] = False
    return result
