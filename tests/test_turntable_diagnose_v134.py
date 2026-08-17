import math
import sqlite3
import struct
from pathlib import Path

import numpy as np

from tools.turntable_diagnose_v134 import (
    MAX_IMAGE_ID,
    axis_from_rotation,
    dominant_axis,
    diagnose_database,
)


def _rot(axis, angle_deg):
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    a = math.radians(angle_deg)
    c, s, q = math.cos(a), math.sin(a), 1.0 - math.cos(a)
    return np.array([
        [c + x*x*q, x*y*q - z*s, x*z*q + y*s],
        [y*x*q + z*s, c + y*y*q, y*z*q - x*s],
        [z*x*q - y*s, z*y*q + x*s, c + z*z*q],
    ])


def _essential_from_rotation(rotation, translation=(1.0, 0.0, 0.0)):
    tx, ty, tz = translation
    skew = np.array([[0.0, -tz, ty], [tz, 0.0, -tx], [-ty, tx, 0.0]])
    return skew @ rotation


def _pair_id(a, b):
    return MAX_IMAGE_ID * min(a, b) + max(a, b)


def test_axis_from_rotation_recovers_tilted_axis_line():
    expected = np.array([0.18, 0.965, -0.19])
    expected /= np.linalg.norm(expected)
    recovered = axis_from_rotation(_rot(expected, 12.0))
    assert abs(float(np.dot(expected, recovered))) > 0.999


def test_dominant_axis_is_sign_invariant():
    expected = np.array([0.2, 0.94, 0.27])
    expected /= np.linalg.norm(expected)
    measurements = [
        {"axis_xyz": expected.tolist(), "angle_rad": math.radians(8), "inliers": 40},
        {"axis_xyz": (-expected).tolist(), "angle_rad": math.radians(11), "inliers": 60},
        {"axis_xyz": expected.tolist(), "angle_rad": math.radians(6), "inliers": 35},
    ]
    result = dominant_axis(measurements)
    assert abs(float(np.dot(expected, result["axis_xyz"]))) > 0.999
    assert result["samples"] == 3
    assert result["median_deviation_deg"] < 0.1


def test_database_diagnostic_flags_axis_mismatch_and_reports_feature_coverage(tmp_path):
    db = tmp_path / "database.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB)")
    con.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)")
    con.execute("CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
    con.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, config INTEGER, F BLOB, E BLOB, H BLOB, qvec BLOB, tvec BLOB)")
    con.execute("INSERT INTO cameras VALUES (1,2,1280,720,?)", (struct.pack('<4d', 900.0, 640.0, 360.0, 0.0),))
    ids = [1, 2, 3, 4, 5]
    for idx, image_id in enumerate(ids):
        con.execute("INSERT INTO images VALUES (?,?,1)", (image_id, f'frame_{idx+1:04d}.jpg'))
        con.execute("INSERT INTO keypoints VALUES (?,?,4,?)", (image_id, 450 + idx * 10, b''))

    axis = np.array([0.3, 0.9, 0.3], dtype=np.float64)
    axis /= np.linalg.norm(axis)
    K = np.array([[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]])
    Kinv = np.linalg.inv(K)
    for left, right, angle, inliers in [(1,2,8,30),(2,3,9,32),(3,4,7,28),(4,5,8,31),(1,3,17,35)]:
        E = _essential_from_rotation(_rot(axis, angle))
        # F is included as a fallback-consistent value even though E is present.
        F = Kinv.T @ E @ Kinv
        con.execute(
            "INSERT INTO two_view_geometries VALUES (?,?,0,?,2,?,?,?,?,?)",
            (_pair_id(left, right), inliers, b'', F.astype('<f8').tobytes(), E.astype('<f8').tobytes(), b'', b'', b''),
        )
    con.commit(); con.close()

    report = diagnose_database(db, min_inliers=12, max_gap=10)
    assert report["image_count"] == 5
    assert report["keypoints"]["median"] >= 450
    assert report["geometry"]["gap_coverage_ratio"] == 1.0
    assert report["rotation_axis"]["samples"] >= 4
    assert report["rotation_axis"]["axis_vs_camera_y_deg"] > 15.0
    assert "hardcoded Y-axis is likely wrong" in report["findings"]
