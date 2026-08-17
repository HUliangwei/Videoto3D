import math
import sqlite3

import numpy as np
import pytest

from pipeline.turntable_angle import (
    estimate_adaptive_turntable_angles,
    fit_turntable_rotation_from_correspondences,
    image_ids_to_pair_id,
    read_turntable_constrained_constraints,
    infer_turntable_tvec_from_run,
)


def _ry(angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=np.float64)


def _skew(vector):
    x, y, z = (float(v) for v in vector)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)


def _essential(angle, tvec):
    rotation = _ry(angle)
    translation = np.asarray(tvec, dtype=np.float64) - rotation @ np.asarray(tvec, dtype=np.float64)
    return _skew(translation) @ rotation


def _project(points, angle, camera, tvec):
    f, cx, cy, k = camera["params"]
    rotation = _ry(angle)
    camera_points = (rotation @ points.T).T + np.asarray(tvec, dtype=np.float64)
    normalized = camera_points[:, :2] / camera_points[:, 2:3]
    radius2 = np.sum(normalized * normalized, axis=1, keepdims=True)
    distorted = normalized * (1.0 + float(k) * radius2)
    return np.column_stack((f * distorted[:, 0] + cx, f * distorted[:, 1] + cy))


def _synthetic_points(count=180, seed=11):
    rng = np.random.default_rng(seed)
    return rng.uniform(
        low=np.array([-0.28, -0.48, -0.22]),
        high=np.array([0.28, 0.48, 0.22]),
        size=(count, 3),
    )


def _camera():
    return {
        "model_name": "SIMPLE_RADIAL",
        "params": (1000.0, 640.0, 360.0, 0.012),
    }


def test_constrained_correspondence_fit_recovers_turntable_angle_with_pixel_noise():
    camera = _camera()
    tvec = (0.045, -0.03, 1.0)
    points = _synthetic_points()
    rng = np.random.default_rng(21)
    left = _project(points, math.radians(3.0), camera, tvec)
    right = _project(points, math.radians(10.35), camera, tvec)
    left += rng.normal(0.0, 0.30, size=left.shape)
    right += rng.normal(0.0, 0.30, size=right.shape)

    fitted = fit_turntable_rotation_from_correspondences(
        left,
        right,
        camera,
        tvec,
        max_angle_deg=20.0,
    )

    assert math.degrees(fitted["angle_rad"]) == pytest.approx(7.35, abs=0.25)
    assert fitted["median_sampson_px"] < 0.8
    assert fitted["direction_sign"] in (-1, 1)


def _make_constrained_db(path, image_ids, angles_deg, camera, tvec, edges, seed=31):
    points = _synthetic_points(count=160, seed=seed)
    rng = np.random.default_rng(seed + 1)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)"
    )
    con.execute(
        "CREATE TABLE two_view_geometries "
        "(pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, "
        "config INTEGER, F BLOB, E BLOB, H BLOB)"
    )

    per_image = {}
    for frame_index, image_id in enumerate(image_ids):
        pixels = _project(points, math.radians(angles_deg[frame_index]), camera, tvec)
        pixels += rng.normal(0.0, 0.22, size=pixels.shape)
        permutation = rng.permutation(len(points))
        inverse = np.empty(len(points), dtype=np.int64)
        inverse[permutation] = np.arange(len(points))
        stored = pixels[permutation].astype(np.float32)
        per_image[image_id] = inverse
        con.execute(
            "INSERT INTO keypoints VALUES (?,?,?,?)",
            (int(image_id), len(stored), 2, stored.tobytes()),
        )

    for left_index, right_index in edges:
        left_id = int(image_ids[left_index])
        right_id = int(image_ids[right_index])
        id1, id2 = sorted((left_id, right_id))
        matches = np.column_stack((per_image[id1], per_image[id2])).astype(np.uint32)
        delta = math.radians(float(angles_deg[right_index] - angles_deg[left_index]))
        signed_delta = delta if left_id == id1 else -delta
        e = _essential(signed_delta, tvec)
        con.execute(
            "INSERT INTO two_view_geometries VALUES (?,?,?,?,?,?,?,?)",
            (
                image_ids_to_pair_id(id1, id2),
                len(matches),
                2,
                matches.tobytes(),
                2,
                None,
                e.astype(np.float64).tobytes(),
                None,
            ),
        )
    con.commit()
    con.close()


def _scene(image_ids, camera):
    return [
        {"image_id": int(image_id), "name": f"frame_{index:04d}.jpg", "camera_id": 1}
        for index, image_id in enumerate(image_ids, 1)
    ], camera


def test_constrained_database_reader_handles_nonmonotonic_colmap_ids(tmp_path):
    db = tmp_path / "database.db"
    camera = _camera()
    tvec = (0.04, 0.01, 1.0)
    image_ids = [40, 7, 31]
    angles = [0.0, 6.2, 13.7]
    _make_constrained_db(db, image_ids, angles, camera, tvec, [(0, 1), (1, 2)])
    images, camera = _scene(image_ids, camera)

    result = read_turntable_constrained_constraints(
        db,
        images,
        camera,
        tvec,
        min_inliers=12,
        max_gap=4,
        max_model_error_px=2.0,
    )

    constraints = result["constraints"]
    assert [(item["left"], item["right"]) for item in constraints] == [(0, 1), (1, 2)]
    assert [math.degrees(item["angle_rad"]) for item in constraints] == pytest.approx([6.2, 7.5], abs=0.3)
    assert all(item["model_error_px"] < 1.0 for item in constraints)
    assert len(result["comparisons"]) == 2


def test_v134_estimator_prefers_constrained_geometry_and_preserves_free_span(tmp_path):
    db = tmp_path / "database.db"
    camera = _camera()
    tvec = (0.035, -0.02, 1.0)
    image_ids = [31, 7, 40, 12, 55, 20]
    increments = [3.0, 5.0, 2.0, 7.0, 4.0]
    angles = np.cumsum([0.0] + increments).tolist()
    edges = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (0, 5)]
    _make_constrained_db(db, image_ids, angles, camera, tvec, edges)
    images, camera = _scene(image_ids, camera)

    result = estimate_adaptive_turntable_angles(
        db,
        images,
        camera,
        tvec=tvec,
        max_gap=10,
    )
    report = result["report"]

    assert report["angle_estimator"] == "turntable_constrained_essential_v134"
    assert report["forced_full_turn"] is False
    assert report["constrained_valid_pairs"] == len(edges)
    assert report["constrained_pair_coverage_ratio"] == pytest.approx(1.0)
    assert report["median_model_residual_px"] < 1.0
    assert report["total_span_deg"] == pytest.approx(sum(increments), abs=1.0)
    assert report["estimated_increment_deg"] == pytest.approx(increments, abs=0.8)
    assert len(report["pair_comparison"]) == len(edges)



def test_mask_center_inference_matches_existing_turntable_translation_contract(tmp_path):
    from PIL import Image, ImageDraw

    run_root = tmp_path / "run"
    colmap = run_root / "colmap"
    masks = run_root / "masks"
    colmap.mkdir(parents=True)
    masks.mkdir(parents=True)
    db = colmap / "database.db"
    db.write_bytes(b"")
    camera = _camera()
    images = []
    for index, center_x in enumerate((620, 640, 660), 1):
        name = f"frame_{index:04d}.jpg"
        images.append({"image_id": index, "name": name, "camera_id": 1})
        image = Image.new("L", (1280, 720), 0)
        ImageDraw.Draw(image).rectangle((center_x - 20, 330, center_x + 20, 390), fill=255)
        image.save(masks / (name + ".png"))

    result = infer_turntable_tvec_from_run(db, images, camera)
    assert result["source"] == "sam2_mask_median"
    assert result["mask_samples"] == 3
    assert result["axis_px"][0] == pytest.approx(640.5, abs=1.0)
    assert result["tvec"][0] == pytest.approx(0.0, abs=0.002)
    assert result["tvec"][2] == 1.0


def test_constrained_estimator_ignores_misleading_generic_e_rotation(tmp_path):
    db = tmp_path / "database.db"
    camera = _camera()
    tvec = (0.035, -0.02, 1.0)
    image_ids = [31, 7, 40, 12, 55, 20]
    increments = [3.0, 5.0, 2.0, 7.0, 4.0]
    angles = np.cumsum([0.0] + increments).tolist()
    edges = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (0, 5)]
    _make_constrained_db(db, image_ids, angles, camera, tvec, edges, seed=44)

    # Deliberately make the stored generic E rotations imply 15 degrees per
    # frame-gap. Verified correspondences remain generated from the true motion.
    con = sqlite3.connect(db)
    rows = con.execute("SELECT pair_id FROM two_view_geometries").fetchall()
    index_by_id = {int(image_id): index for index, image_id in enumerate(image_ids)}
    for (pair_id,) in rows:
        from pipeline.turntable_angle import pair_id_to_image_ids
        id1, id2 = pair_id_to_image_ids(pair_id)
        gap = abs(index_by_id[id2] - index_by_id[id1])
        fake_angle = math.radians(15.0 * gap)
        fake_e = _skew((0.16, 0.03, 0.78)) @ _ry(fake_angle)
        con.execute(
            "UPDATE two_view_geometries SET E=? WHERE pair_id=?",
            (fake_e.astype(np.float64).tobytes(), int(pair_id)),
        )
    con.commit()
    con.close()

    images, camera = _scene(image_ids, camera)
    report = estimate_adaptive_turntable_angles(
        db,
        images,
        camera,
        tvec=tvec,
        max_gap=10,
    )["report"]

    assert report["angle_estimator"] == "turntable_constrained_essential_v134"
    assert report["total_span_deg"] == pytest.approx(sum(increments), abs=1.0)
    assert report["legacy_total_span_deg"] is not None
    assert report["legacy_total_span_deg"] > 50.0
    assert abs(report["legacy_total_span_deg"] - report["total_span_deg"]) > 25.0
