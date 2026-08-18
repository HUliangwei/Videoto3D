"""Read-only diagnostics for Videoto3D Turntable sparse reconstruction.

This tool does not modify the COLMAP database or any reconstruction output. It
measures feature density, verified-pair coverage, and the dominant 3-D rotation
axis implied by COLMAP two-view geometry so V1.3.4 can distinguish pose-model
errors from weak feature matching before changing production reconstruction.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import struct
from pathlib import Path

import numpy as np

MAX_IMAGE_ID = 2147483647
_SIMPLE_RADIAL_MODEL_ID = 2


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


def _camera_matrix(params):
    f, cx, cy, _k = (float(v) for v in params)
    return np.array([[f, 0.0, cx], [0.0, f, cy], [0.0, 0.0, 1.0]], dtype=np.float64)


def decompose_essential_rotation(essential):
    """Return the smaller-angle rotation matrix implied by an essential matrix."""
    e = np.asarray(essential, dtype=np.float64).reshape(3, 3)
    if not np.all(np.isfinite(e)) or float(np.linalg.norm(e)) <= 1e-12:
        raise ValueError("degenerate essential matrix")
    u, _s, vt = np.linalg.svd(e)
    if np.linalg.det(u) < 0:
        u[:, -1] *= -1.0
    if np.linalg.det(vt) < 0:
        vt[-1, :] *= -1.0
    w = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    candidates = []
    for rotation in (u @ w @ vt, u @ w.T @ vt):
        if np.linalg.det(rotation) < 0:
            rotation = -rotation
        value = float((np.trace(rotation) - 1.0) * 0.5)
        angle = math.acos(max(-1.0, min(1.0, value)))
        candidates.append((angle, rotation))
    return min(candidates, key=lambda item: item[0])


def axis_from_rotation(rotation):
    """Return the unsigned unit rotation axis for a proper rotation matrix."""
    r = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    values, vectors = np.linalg.eig(r)
    index = int(np.argmin(np.abs(values - 1.0)))
    axis = np.real(vectors[:, index]).astype(np.float64)
    norm = float(np.linalg.norm(axis))
    if not math.isfinite(norm) or norm <= 1e-9:
        raise ValueError("rotation axis is degenerate")
    axis /= norm
    return axis


def _median(values):
    values = sorted(float(v) for v in values)
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return 0.5 * (values[middle - 1] + values[middle])


def dominant_axis(measurements, min_angle_deg=0.5):
    usable = []
    for item in measurements:
        angle = float(item.get("angle_rad", 0.0))
        axis = np.asarray(item.get("axis_xyz", ()), dtype=np.float64)
        if axis.size != 3 or angle < math.radians(float(min_angle_deg)):
            continue
        norm = float(np.linalg.norm(axis))
        if not math.isfinite(norm) or norm <= 1e-9:
            continue
        axis /= norm
        weight = math.sqrt(max(1.0, float(item.get("inliers", 1)))) * max(math.sin(angle), 0.05)
        usable.append((axis, weight))
    if len(usable) < 3:
        return {
            "axis_xyz": [0.0, 1.0, 0.0],
            "samples": len(usable),
            "median_deviation_deg": None,
            "fallback_camera_y": True,
        }

    scatter = np.zeros((3, 3), dtype=np.float64)
    for axis, weight in usable:
        scatter += float(weight) * np.outer(axis, axis)
    values, vectors = np.linalg.eigh(scatter)
    axis = vectors[:, int(np.argmax(values))]
    axis /= np.linalg.norm(axis)
    # Canonicalize only for readable JSON. The physical axis is an unsigned line.
    if axis[1] < 0 or (abs(axis[1]) < 1e-9 and axis[2] < 0):
        axis = -axis

    deviations = []
    for sample, _weight in usable:
        dot = max(-1.0, min(1.0, abs(float(np.dot(axis, sample)))))
        deviations.append(math.degrees(math.acos(dot)))
    return {
        "axis_xyz": [float(v) for v in axis],
        "samples": len(usable),
        "median_deviation_deg": float(_median(deviations)),
        "max_deviation_deg": float(max(deviations)),
        "fallback_camera_y": False,
    }


def _read_scene(connection):
    cameras = connection.execute(
        "SELECT camera_id, model, width, height, params FROM cameras ORDER BY camera_id"
    ).fetchall()
    if len(cameras) != 1:
        raise RuntimeError("Turntable diagnostic expects one shared camera; found {}.".format(len(cameras)))
    camera_id, model_id, width, height, params_blob = cameras[0]
    if int(model_id) != _SIMPLE_RADIAL_MODEL_ID:
        raise RuntimeError("Turntable diagnostic expects SIMPLE_RADIAL camera model id 2.")
    params = struct.unpack("<{}d".format(len(params_blob) // 8), params_blob)
    if len(params) != 4:
        raise RuntimeError("SIMPLE_RADIAL camera params must be [f,cx,cy,k].")
    images = connection.execute(
        "SELECT image_id, name, camera_id FROM images ORDER BY name"
    ).fetchall()
    return {
        "camera_id": int(camera_id),
        "width": int(width),
        "height": int(height),
        "params": tuple(float(v) for v in params),
    }, images


def diagnose_database(database_path, min_inliers=12, max_gap=10):
    database_path = Path(database_path)
    connection = sqlite3.connect(str(database_path))
    try:
        camera, images = _read_scene(connection)
        by_id = {int(row[0]): index for index, row in enumerate(images)}
        keypoint_rows = dict(
            (int(image_id), int(rows or 0))
            for image_id, rows in connection.execute("SELECT image_id, rows FROM keypoints").fetchall()
        )
        geometry_rows = connection.execute(
            "SELECT pair_id, rows, F, E FROM two_view_geometries WHERE rows>=?",
            (int(min_inliers),),
        ).fetchall()
    finally:
        connection.close()

    k = _camera_matrix(camera["params"])
    measurements = []
    covered = np.zeros(max(len(images) - 1, 0), dtype=bool)
    adjacent = 0
    temporal_pairs = 0
    inlier_counts = []
    per_gap = {}

    for pair_id, inliers, f_blob, e_blob in geometry_rows:
        image_id1, image_id2 = pair_id_to_image_ids(pair_id)
        if image_id1 not in by_id or image_id2 not in by_id:
            continue
        left, right = by_id[image_id1], by_id[image_id2]
        reverse = left > right
        if reverse:
            left, right = right, left
        gap = right - left
        if gap <= 0 or gap > int(max_gap):
            continue
        e = _blob_matrix(e_blob)
        if e is None:
            f = _blob_matrix(f_blob)
            if f is not None:
                e = k.T @ f @ k
        if e is None:
            continue
        try:
            angle, rotation = decompose_essential_rotation(e)
            if reverse:
                rotation = rotation.T
            axis = axis_from_rotation(rotation)
        except Exception:
            continue
        if not math.isfinite(angle) or angle <= math.radians(0.01) or angle >= math.radians(120.0):
            continue
        temporal_pairs += 1
        if gap == 1:
            adjacent += 1
        if len(covered):
            covered[left:right] = True
        inlier_counts.append(int(inliers or 0))
        per_gap[str(gap)] = per_gap.get(str(gap), 0) + 1
        measurements.append({
            "left": int(left),
            "right": int(right),
            "gap": int(gap),
            "angle_rad": float(angle),
            "axis_xyz": [float(v) for v in axis],
            "inliers": int(inliers or 0),
        })

    axis_report = dominant_axis(measurements)
    axis = np.asarray(axis_report["axis_xyz"], dtype=np.float64)
    y_dot = max(-1.0, min(1.0, abs(float(np.dot(axis, np.array([0.0, 1.0, 0.0]))))))
    axis_report["axis_vs_camera_y_deg"] = float(math.degrees(math.acos(y_dot)))

    keypoint_counts = [keypoint_rows.get(int(row[0]), 0) for row in images]
    expected_gaps = max(len(images) - 1, 1)
    findings = []
    if not axis_report["fallback_camera_y"] and axis_report["axis_vs_camera_y_deg"] > 8.0:
        findings.append("hardcoded Y-axis is likely wrong")
    if axis_report.get("median_deviation_deg") is not None and axis_report["median_deviation_deg"] > 10.0:
        findings.append("relative-rotation axes are internally inconsistent")
    coverage = float(np.count_nonzero(covered)) / float(expected_gaps) if len(covered) else 0.0
    if coverage < 0.65:
        findings.append("verified temporal-pair coverage is low")
    median_keypoints = _median(keypoint_counts) or 0.0
    if median_keypoints < 500:
        findings.append("foreground SIFT feature density is low")
    if not findings:
        findings.append("no dominant diagnostic warning")

    return {
        "database": str(database_path),
        "image_count": len(images),
        "camera": {
            "width": camera["width"],
            "height": camera["height"],
            "focal_length_px": camera["params"][0],
        },
        "keypoints": {
            "min": int(min(keypoint_counts)) if keypoint_counts else 0,
            "median": float(median_keypoints),
            "max": int(max(keypoint_counts)) if keypoint_counts else 0,
            "total": int(sum(keypoint_counts)),
        },
        "geometry": {
            "min_inliers": int(min_inliers),
            "max_gap": int(max_gap),
            "verified_temporal_pairs": int(temporal_pairs),
            "adjacent_verified_pairs": int(adjacent),
            "adjacent_valid_ratio": float(adjacent) / float(expected_gaps),
            "gap_coverage_ratio": coverage,
            "median_inliers": float(_median(inlier_counts) or 0.0),
            "pairs_by_gap": per_gap,
        },
        "rotation_axis": axis_report,
        "findings": findings,
    }


def diagnose_run(project_root, run_id, output_path=None):
    root = Path(project_root).resolve()
    database = root / "workspace" / "runs" / str(run_id) / "colmap" / "database.db"
    if not database.exists():
        raise FileNotFoundError("COLMAP database not found: {}".format(database))
    report = diagnose_database(database)
    if output_path is None:
        output_path = database.parent / "turntable_diagnostic_v134.json"
    output_path = Path(output_path)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diagnose Turntable pose/matching quality without changing reconstruction.")
    parser.add_argument("--run", required=True, dest="run_id")
    parser.add_argument("--root", default=".", dest="project_root")
    args = parser.parse_args(argv)
    report, path = diagnose_run(args.project_root, args.run_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nReport:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
