
import math
import sqlite3
import struct

import numpy as np
import pytest

from pipeline.turntable_angle import (
    cumulative_angles_from_increments,
    estimate_adaptive_turntable_angles,
    estimate_relative_rotation_from_essential,
    image_ids_to_pair_id,
    read_adjacent_pair_rotations,
    smooth_and_normalize_increments,
)


def ry(angle):
    return np.array([
        [math.cos(angle), 0.0, math.sin(angle)],
        [0.0, 1.0, 0.0],
        [-math.sin(angle), 0.0, math.cos(angle)],
    ], dtype=np.float64)


def skew(t):
    x, y, z = t
    return np.array([
        [0.0, -z, y],
        [z, 0.0, -x],
        [-y, x, 0.0],
    ], dtype=np.float64)


@pytest.mark.parametrize("degrees", [1.5, 4.0, 9.0, 18.0])
def test_essential_decomposition_recovers_small_rotation(degrees):
    expected = math.radians(degrees)
    e = skew((0.2, 0.0, 0.7)) @ ry(expected)
    actual = estimate_relative_rotation_from_essential(e)
    assert actual == pytest.approx(expected, abs=1e-7)


def test_pair_id_is_order_independent():
    assert image_ids_to_pair_id(11, 23) == image_ids_to_pair_id(23, 11)


def make_geometry_db(path, image_ids, increments_deg):
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE two_view_geometries "
        "(pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, "
        "config INTEGER, F BLOB, E BLOB, H BLOB)"
    )
    for left, right, degrees in zip(image_ids[:-1], image_ids[1:], increments_deg):
        e = skew((0.15, 0.02, 0.8)) @ ry(math.radians(degrees))
        con.execute(
            "INSERT INTO two_view_geometries VALUES (?,?,?,?,?,?,?,?)",
            (
                image_ids_to_pair_id(left, right),
                60,
                2,
                b"",
                2,
                None,
                e.astype(np.float64).tobytes(),
                None,
            ),
        )
    con.commit()
    con.close()


def test_database_adjacent_geometry_preserves_nonuniform_speed(tmp_path):
    db = tmp_path / "database.db"
    ids = [3, 7, 10, 18, 29]
    expected_deg = [2.0, 8.0, 4.0, 14.0]
    make_geometry_db(db, ids, expected_deg)
    images = [
        {"image_id": image_id, "name": f"frame_{index:04d}.jpg", "camera_id": 1}
        for index, image_id in enumerate(ids, 1)
    ]
    camera = {
        "model_name": "SIMPLE_RADIAL",
        "params": (1000.0, 640.0, 360.0, 0.0),
    }
    measured = read_adjacent_pair_rotations(db, images, camera)
    assert [math.degrees(x) for x in measured] == pytest.approx(expected_deg, abs=1e-5)


def test_smoothing_retains_speed_variation_and_normalizes_full_turn():
    raw = [math.radians(v) for v in [2, 4, 8, 5, 12, 4, 3, 9, 5]]
    result = smooth_and_normalize_increments(raw, frame_count=10)
    assert result["fallback_uniform"] is False
    values = result["increments_rad"]
    assert max(values) / min(values) > 2.0
    expected_span = 2.0 * math.pi * 9.0 / 10.0
    assert sum(values) == pytest.approx(expected_span, rel=1e-9)


def test_sparse_geometry_falls_back_to_uniform_when_too_many_pairs_missing():
    raw = [None, None, math.radians(5), None, None, None, None, None, None]
    result = smooth_and_normalize_increments(raw, frame_count=10)
    assert result["fallback_uniform"] is True
    assert len(set(round(v, 12) for v in result["increments_rad"])) == 1


def test_adaptive_result_produces_monotonic_cumulative_angles(tmp_path):
    db = tmp_path / "database.db"
    ids = [1, 2, 3, 4, 5, 6]
    make_geometry_db(db, ids, [2, 5, 9, 3, 11])
    images = [
        {"image_id": image_id, "name": f"frame_{index:04d}.jpg", "camera_id": 1}
        for index, image_id in enumerate(ids, 1)
    ]
    camera = {
        "model_name": "SIMPLE_RADIAL",
        "params": (1000.0, 640.0, 360.0, 0.0),
    }
    result = estimate_adaptive_turntable_angles(db, images, camera)
    angles = result["angles_rad"]
    assert len(angles) == len(images)
    assert all(b > a for a, b in zip(angles[:-1], angles[1:]))
    assert result["report"]["strategy"] == "adaptive_360_epipolar"
    assert result["report"]["valid_pair_ratio"] == 1.0
