import math
import sqlite3

import numpy as np
import pytest

from pipeline.turntable_angle import (
    cumulative_angles_from_increments,
    estimate_adaptive_turntable_angles,
    estimate_relative_rotation_from_essential,
    image_ids_to_pair_id,
    pair_id_to_image_ids,
    read_adjacent_pair_rotations,
    read_pair_rotation_constraints,
    smooth_and_normalize_increments,
    solve_free_span_increments,
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


def test_pair_id_round_trip_and_order_independence():
    pair_id = image_ids_to_pair_id(11, 23)
    assert pair_id == image_ids_to_pair_id(23, 11)
    assert pair_id_to_image_ids(pair_id) == (11, 23)


def make_geometry_db(path, image_ids, edge_degrees):
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE two_view_geometries "
        "(pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, "
        "config INTEGER, F BLOB, E BLOB, H BLOB)"
    )
    for left_index, right_index, degrees in edge_degrees:
        e = skew((0.15, 0.02, 0.8)) @ ry(math.radians(degrees))
        con.execute(
            "INSERT INTO two_view_geometries VALUES (?,?,?,?,?,?,?,?)",
            (
                image_ids_to_pair_id(image_ids[left_index], image_ids[right_index]),
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


def scene(image_ids):
    images = [
        {"image_id": image_id, "name": f"frame_{index:04d}.jpg", "camera_id": 1}
        for index, image_id in enumerate(image_ids, 1)
    ]
    camera = {
        "model_name": "SIMPLE_RADIAL",
        "params": (1000.0, 640.0, 360.0, 0.0),
    }
    return images, camera


def test_database_adjacent_geometry_preserves_nonuniform_speed(tmp_path):
    db = tmp_path / "database.db"
    ids = [3, 7, 10, 18, 29]
    expected_deg = [2.0, 8.0, 4.0, 14.0]
    make_geometry_db(db, ids, [(i, i + 1, value) for i, value in enumerate(expected_deg)])
    images, camera = scene(ids)
    measured = read_adjacent_pair_rotations(db, images, camera)
    assert [math.degrees(x) for x in measured] == pytest.approx(expected_deg, abs=1e-5)


def test_multi_pair_reader_uses_non_adjacent_verified_geometry(tmp_path):
    db = tmp_path / "database.db"
    ids = [2, 4, 8, 16, 32]
    make_geometry_db(db, ids, [(0, 2, 11.0), (1, 4, 19.0), (3, 4, 4.0)])
    images, camera = scene(ids)
    constraints = read_pair_rotation_constraints(db, images, camera, max_gap=10)
    assert [(item["left"], item["right"]) for item in constraints] == [(0, 2), (1, 4), (3, 4)]
    assert [math.degrees(item["angle_rad"]) for item in constraints] == pytest.approx([11.0, 19.0, 4.0], abs=1e-5)


def test_free_span_graph_recovers_nonuniform_motion_without_360_normalization():
    true_deg = [2.0, 6.0, 3.0, 8.0, 4.0]
    cumulative = np.cumsum([0.0] + true_deg)
    pairs = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (1, 5)]
    constraints = [
        {
            "left": left,
            "right": right,
            "gap": right - left,
            "angle_rad": math.radians(float(cumulative[right] - cumulative[left])),
            "inliers": 80,
        }
        for left, right in pairs
    ]
    solved = solve_free_span_increments(constraints, frame_count=6)
    actual_deg = [math.degrees(value) for value in solved["increments_rad"]]
    assert actual_deg == pytest.approx(true_deg, abs=0.35)
    assert sum(actual_deg) == pytest.approx(sum(true_deg), abs=0.5)
    assert sum(actual_deg) < 30.0


def test_free_span_graph_bridges_missing_adjacent_pairs(tmp_path):
    db = tmp_path / "database.db"
    ids = [1, 2, 3, 4, 5, 6]
    true_deg = [3.0, 5.0, 2.0, 7.0, 4.0]
    cumulative = np.cumsum([0.0] + true_deg)
    # Only two adjacent edges are present; multi-frame edges carry the rest.
    pairs = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (0, 5)]
    edges = [
        (left, right, float(cumulative[right] - cumulative[left]))
        for left, right in pairs
    ]
    make_geometry_db(db, ids, edges)
    images, camera = scene(ids)
    result = estimate_adaptive_turntable_angles(db, images, camera, max_gap=10)
    estimated = result["report"]["estimated_increment_deg"]
    assert estimated == pytest.approx(true_deg, abs=0.6)
    assert result["report"]["strategy"] == "adaptive_free_span_graph"
    assert result["report"]["forced_full_turn"] is False
    assert result["report"]["total_span_deg"] == pytest.approx(sum(true_deg), abs=0.8)
    assert result["report"]["graph_gap_coverage_ratio"] == pytest.approx(1.0)
    assert result["report"]["angle_estimator"] == "legacy_generic_essential_fallback"
    assert result["report"]["constrained_valid_pairs"] == 0


def test_solver_rejects_geometry_that_is_too_sparse():
    with pytest.raises(RuntimeError, match="at least 3 verified temporal pairs"):
        solve_free_span_increments([
            {"left": 0, "right": 1, "gap": 1, "angle_rad": math.radians(4), "inliers": 20},
            {"left": 1, "right": 2, "gap": 1, "angle_rad": math.radians(5), "inliers": 20},
        ], frame_count=5)


def test_legacy_smoothing_helper_keeps_v132_full_turn_semantics():
    raw = [math.radians(v) for v in [2, 4, 8, 5, 12, 4, 3, 9, 5]]
    result = smooth_and_normalize_increments(raw, frame_count=10)
    expected_span = 2.0 * math.pi * 9.0 / 10.0
    assert sum(result["increments_rad"]) == pytest.approx(expected_span, rel=1e-9)


def test_cumulative_angles_are_strictly_monotonic():
    angles = cumulative_angles_from_increments([math.radians(v) for v in [2, 7, 3, 9]])
    assert all(b > a for a, b in zip(angles[:-1], angles[1:]))


def test_pair_reader_rejects_implausible_per_gap_jump_but_keeps_multiframe_motion(tmp_path):
    db = tmp_path / "database.db"
    ids = [1, 2, 3, 4, 5]
    # 36 degrees in one gap is implausible for the low-cost Turntable contract;
    # the same 36 degrees across four gaps is only 9 degrees/gap and remains valid.
    make_geometry_db(db, ids, [(0, 1, 36.0), (0, 4, 36.0)])
    images, camera = scene(ids)
    constraints = read_pair_rotation_constraints(db, images, camera, max_gap=10)
    assert [(item["left"], item["right"]) for item in constraints] == [(0, 4)]


def test_free_span_report_exposes_confidence_without_forcing_360(tmp_path):
    db = tmp_path / "database.db"
    ids = [1, 2, 3, 4, 5, 6]
    true_deg = [3.0, 5.0, 2.0, 7.0, 4.0]
    cumulative = np.cumsum([0.0] + true_deg)
    pairs = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (0, 5)]
    make_geometry_db(db, ids, [
        (left, right, float(cumulative[right] - cumulative[left]))
        for left, right in pairs
    ])
    images, camera = scene(ids)
    result = estimate_adaptive_turntable_angles(db, images, camera)
    report = result["report"]
    assert report["confidence"] in {"high", "medium", "low"}
    assert isinstance(report["confidence_reasons"], list) and report["confidence_reasons"]
    assert report["max_step_rotation_deg"] == pytest.approx(20.0)
    assert report["forced_full_turn"] is False
    assert report["total_span_deg"] < 60.0
