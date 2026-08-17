"""Turntable reconstruction with deterministic uniform-360 known camera poses.

Orbit Camera remains on the existing incremental SfM path. This module is used
only for manually selected Turntable capture: fixed, approximately level camera;
rigid subject; one approximately complete 360-degree rotation. Per-frame speed may vary.
"""

from __future__ import annotations

import math
import os
import shutil
import sqlite3
import statistics
import struct
import subprocess
from pathlib import Path

from PIL import Image

from pipeline.turntable_angle import (
    estimate_adaptive_turntable_angles,
    write_angle_report,
)

_SIMPLE_RADIAL_MODEL_ID = 2
_SIMPLE_RADIAL_NAME = "SIMPLE_RADIAL"


def _build_colmap_command(colmap_path, args):
    colmap_path = Path(colmap_path)
    if colmap_path.suffix.lower() in (".bat", ".cmd"):
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(colmap_path),
        ] + list(args)
    return [str(colmap_path)] + list(args)


def _run_stage(colmap_path, args, log_path, cwd):
    result = subprocess.run(
        _build_colmap_command(colmap_path, args),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(result.stdout or "", encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(
            "COLMAP stage '{}' failed with exit code {}. See {}".format(
                args[0], result.returncode, log_path
            )
        )
    return result.stdout or ""


def _parse_analyzer_stats(text):
    import re

    stats = {}
    patterns = {
        "registered_images": [r"Registered images:\s*(\d+)", r"Images:\s*(\d+)"],
        "points3D": [r"Points:\s*(\d+)", r"3D points:\s*(\d+)"],
        "mean_track_length": [r"Mean track length:\s*([0-9.]+)"],
        "mean_reprojection_error": [r"Mean reprojection error:\s*([0-9.]+)"],
    }
    for key, candidates in patterns.items():
        for pattern in candidates:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1)
                stats[key] = (
                    int(value)
                    if key in ("registered_images", "points3D")
                    else float(value)
                )
                break
    return stats


def read_database_scene(database_path):
    """Read the one shared SIMPLE_RADIAL camera and images in filename order."""
    database_path = Path(database_path)
    connection = sqlite3.connect(str(database_path))
    try:
        cameras = connection.execute(
            "SELECT camera_id, model, width, height, params FROM cameras ORDER BY camera_id"
        ).fetchall()
        if len(cameras) != 1:
            raise RuntimeError(
                "Turntable mode expects one shared camera; found {}.".format(len(cameras))
            )
        camera_id, model_id, width, height, params_blob = cameras[0]
        if int(model_id) != _SIMPLE_RADIAL_MODEL_ID:
            raise RuntimeError(
                "Turntable mode expects SIMPLE_RADIAL camera model id {}; found {}."
                .format(_SIMPLE_RADIAL_MODEL_ID, model_id)
            )
        if params_blob is None or len(params_blob) % 8:
            raise RuntimeError("Invalid COLMAP camera params blob.")
        params = struct.unpack("<{}d".format(len(params_blob) // 8), params_blob)
        if len(params) != 4:
            raise RuntimeError(
                "SIMPLE_RADIAL requires [f,cx,cy,k]; found {} params.".format(len(params))
            )

        image_rows = connection.execute(
            "SELECT image_id, name, camera_id FROM images ORDER BY name"
        ).fetchall()
    finally:
        connection.close()

    if not image_rows:
        raise RuntimeError("COLMAP database contains no images.")

    images = [
        {"image_id": int(i), "name": str(name), "camera_id": int(cid)}
        for i, name, cid in image_rows
    ]
    if any(image["camera_id"] != int(camera_id) for image in images):
        raise RuntimeError("Turntable mode requires all frames to share one camera.")

    camera = {
        "camera_id": int(camera_id),
        "model_id": int(model_id),
        "model_name": _SIMPLE_RADIAL_NAME,
        "width": int(width),
        "height": int(height),
        "params": tuple(float(v) for v in params),
    }
    return camera, images


def estimate_turntable_translation(masks_dir, images, camera):
    """Approximate the projected turntable center from median SAM2 mask boxes."""
    masks_dir = Path(masks_dir)
    xs, ys = [], []
    for image in images:
        mask_path = masks_dir / (image["name"] + ".png")
        if not mask_path.exists():
            continue
        with Image.open(mask_path) as image_mask:
            bbox = image_mask.convert("L").getbbox()
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        xs.append((left + right) * 0.5)
        ys.append((top + bottom) * 0.5)

    if not xs:
        raise RuntimeError("No non-empty SAM2 masks found for Turntable pose setup.")

    u0 = float(statistics.median(xs))
    v0 = float(statistics.median(ys))
    f, cx, cy, _k = camera["params"]
    if not math.isfinite(f) or f <= 0:
        raise RuntimeError("Invalid focal length: {}".format(f))

    # Monocular scale is arbitrary. Set turntable center depth to one unit.
    tz = 1.0
    tx = (u0 - cx) / f
    ty = (v0 - cy) / f
    return {
        "tvec": (float(tx), float(ty), tz),
        "axis_px": (u0, v0),
        "mask_samples": len(xs),
    }


def build_pose_records(images, tvec, angles_rad, direction):
    """Create known poses from a monotonic per-frame angle trajectory."""
    direction = int(direction)
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    if len(images) < 2:
        raise ValueError("Need at least two images.")
    if len(angles_rad) != len(images):
        raise ValueError(
            "Need one angle per image; got {} angles for {} images.".format(
                len(angles_rad), len(images)
            )
        )

    tx, ty, tz = (float(v) for v in tvec)
    records = []
    previous = None
    for image, base_angle in zip(images, angles_rad):
        base_angle = float(base_angle)
        if previous is not None and base_angle <= previous:
            raise ValueError("Turntable angles must be strictly increasing.")
        previous = base_angle

        angle = direction * base_angle
        qvec = (math.cos(angle * 0.5), 0.0, math.sin(angle * 0.5), 0.0)
        records.append(
            {
                "image_id": int(image["image_id"]),
                "camera_id": int(image["camera_id"]),
                "name": str(image["name"]),
                "qvec": qvec,
                "tvec": (tx, ty, tz),
                "angle_rad": angle,
            }
        )
    return records


def build_uniform_pose_records(images, tvec, direction):
    """Backward-compatible uniform pose helper used by existing tests/tools."""
    count = len(images)
    angles = [2.0 * math.pi * float(index) / float(count) for index in range(count)]
    return build_pose_records(images, tvec, angles, direction)


def _rotation_from_qvec(qvec):
    qw, qx, qy, qz = (float(v) for v in qvec)
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n <= 0:
        raise ValueError("Zero quaternion")
    qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    return (
        (
            1 - 2 * (qy * qy + qz * qz),
            2 * (qx * qy - qz * qw),
            2 * (qx * qz + qy * qw),
        ),
        (
            2 * (qx * qy + qz * qw),
            1 - 2 * (qx * qx + qz * qz),
            2 * (qy * qz - qx * qw),
        ),
        (
            2 * (qx * qz - qy * qw),
            2 * (qy * qz + qx * qw),
            1 - 2 * (qx * qx + qy * qy),
        ),
    )


def camera_center_from_qt(qvec, tvec):
    """Return COLMAP camera center C=-R^T t."""
    r = _rotation_from_qvec(qvec)
    tx, ty, tz = (float(v) for v in tvec)
    return tuple(
        -(r[0][axis] * tx + r[1][axis] * ty + r[2][axis] * tz)
        for axis in range(3)
    )


def _fmt(value):
    return "{:.17g}".format(float(value))


def write_known_pose_model(output_dir, camera, poses):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "cameras.txt").write_text(
        "# Camera list\n# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n"
        + "{} {} {} {} {}\n".format(
            camera["camera_id"],
            camera["model_name"],
            camera["width"],
            camera["height"],
            " ".join(_fmt(v) for v in camera["params"]),
        ),
        encoding="utf-8",
    )

    lines = [
        "# Image list with two lines of data per image:",
        "# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME",
        "# POINTS2D[] as (X, Y, POINT3D_ID)",
    ]
    for pose in poses:
        lines.append(
            "{} {} {} {} {}".format(
                pose["image_id"],
                " ".join(_fmt(v) for v in pose["qvec"]),
                " ".join(_fmt(v) for v in pose["tvec"]),
                pose["camera_id"],
                pose["name"],
            )
        )
        lines.append("")
    (output_dir / "images.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "points3D.txt").write_text(
        "# 3D point list\n# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n",
        encoding="utf-8",
    )
    return output_dir


def choose_turntable_candidate(candidates):
    usable = [
        item for item in candidates
        if item.get("stats", {}).get("points3D") is not None
    ]
    if not usable:
        raise RuntimeError("Neither Turntable direction produced a valid sparse model.")

    def score(item):
        stats = item["stats"]
        points = int(stats.get("points3D") or 0)
        error = stats.get("mean_reprojection_error")
        error = float(error) if error is not None else float("inf")
        return (points, -error)

    return max(usable, key=score)


def _feature_args(database_path, frames_dir, masks_dir):
    return [
        "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(frames_dir),
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", _SIMPLE_RADIAL_NAME,
        "--ImageReader.mask_path", str(masks_dir),
        "--FeatureExtraction.use_gpu", "1",
    ]


def _matcher_args(database_path):
    return [
        "sequential_matcher",
        "--database_path", str(database_path),
        "--SequentialMatching.overlap", "10",
        "--SequentialMatching.quadratic_overlap", "1",
        "--FeatureMatching.guided_matching", "1",
        "--FeatureMatching.use_gpu", "1",
    ]


def _triangulator_args(database_path, frames_dir, input_model, output_model):
    return [
        "point_triangulator",
        "--database_path", str(database_path),
        "--image_path", str(frames_dir),
        "--input_path", str(input_model),
        "--output_path", str(output_model),
        "--Mapper.tri_ignore_two_view_tracks", "0",
        "--Mapper.tri_min_angle", "0.1",
    ]


def _valid_binary_model(path):
    path = Path(path)
    return all((path / name).exists() for name in ("cameras.bin","images.bin","points3D.bin"))


def run_turntable_reconstruction(
    colmap_path,
    frames_dir,
    masks_dir,
    colmap_dir,
    logs_dir,
    overwrite=True,
):
    """Build a COLMAP sparse model from adaptive Turntable known poses."""
    colmap_path = Path(colmap_path)
    frames_dir = Path(frames_dir)
    masks_dir = Path(masks_dir)
    colmap_dir = Path(colmap_dir)
    logs_dir = Path(logs_dir)

    if not colmap_path.exists():
        raise FileNotFoundError("COLMAP not found: {}".format(colmap_path))
    frame_count = len(list(frames_dir.glob("frame_*.jpg")))
    if frame_count < 10:
        raise RuntimeError("Turntable mode needs at least 10 frames; found {}.".format(frame_count))

    database_path = colmap_dir / "database.db"
    known_root = colmap_dir / "turntable_known"
    candidates_root = colmap_dir / "turntable_candidates"
    sparse_root = colmap_dir / "sparse"
    final_model = sparse_root / "0"
    colmap_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if overwrite:
        if database_path.exists():
            database_path.unlink()
        for path in (known_root, candidates_root, sparse_root):
            if path.exists():
                shutil.rmtree(path)

    _run_stage(
        colmap_path,
        _feature_args(database_path, frames_dir, masks_dir),
        logs_dir / "colmap_feature_extractor.log",
        colmap_dir,
    )
    _run_stage(
        colmap_path,
        _matcher_args(database_path),
        logs_dir / "colmap_sequential_matcher.log",
        colmap_dir,
    )

    camera, images = read_database_scene(database_path)
    if len(images) != frame_count:
        raise RuntimeError(
            "Database contains {} images but frames contains {}.".format(len(images), frame_count)
        )

    center = estimate_turntable_translation(masks_dir, images, camera)
    angle_result = estimate_adaptive_turntable_angles(
        database_path,
        images,
        camera,
        min_inliers=12,
    )
    angle_report_path = write_angle_report(
        colmap_dir / "turntable_angle_report.json",
        angle_result,
    )
    candidates = []

    for label, sign in (("cw", 1), ("ccw", -1)):
        known_model = known_root / label
        candidate_model = candidates_root / label
        write_known_pose_model(
            known_model,
            camera,
            build_pose_records(
                images,
                center["tvec"],
                angle_result["angles_rad"],
                sign,
            ),
        )
        candidate_model.mkdir(parents=True, exist_ok=True)
        try:
            _run_stage(
                colmap_path,
                _triangulator_args(database_path, frames_dir, known_model, candidate_model),
                logs_dir / ("colmap_point_triangulator_{}.log".format(label)),
                colmap_dir,
            )
            if not _valid_binary_model(candidate_model):
                raise RuntimeError("Incomplete triangulated model: {}".format(candidate_model))
            analyzer = _run_stage(
                colmap_path,
                ["model_analyzer", "--path", str(candidate_model)],
                logs_dir / ("colmap_model_analyzer_{}.log".format(label)),
                colmap_dir,
            )
            candidates.append(
                {
                    "direction": label,
                    "direction_sign": sign,
                    "model": str(candidate_model),
                    "stats": _parse_analyzer_stats(analyzer),
                }
            )
        except Exception as exc:
            (logs_dir / ("colmap_turntable_{}_failure.log".format(label))).write_text(
                str(exc) + "\n", encoding="utf-8"
            )

    selected = choose_turntable_candidate(candidates)
    selected_model = Path(selected["model"])

    if final_model.exists():
        shutil.rmtree(final_model)
    final_model.mkdir(parents=True, exist_ok=True)
    for name in ("cameras.bin","images.bin","points3D.bin"):
        shutil.copy2(selected_model / name, final_model / name)

    final_analyzer = _run_stage(
        colmap_path,
        ["model_analyzer", "--path", str(final_model)],
        logs_dir / "colmap_model_analyzer.log",
        colmap_dir,
    )
    stats = _parse_analyzer_stats(final_analyzer)
    if int(stats.get("points3D") or 0) <= 0:
        raise RuntimeError("Turntable known-pose triangulation produced zero sparse points.")

    return {
        "frame_count": frame_count,
        "database": str(database_path),
        "mask_path": str(masks_dir),
        "sparse_dir": str(sparse_root),
        "model": str(final_model),
        "model_count": 1,
        "stats": stats,
        "turntable": {
            "pose_strategy": angle_result["report"]["strategy"],
            "selected_direction": selected["direction"],
            "selected_direction_sign": selected["direction_sign"],
            "axis_px": list(center["axis_px"]),
            "translation": list(center["tvec"]),
            "mask_samples": center["mask_samples"],
            "angle_report": str(angle_report_path),
            "angle_valid_pair_ratio": angle_result["valid_ratio"],
            "angle_fallback_uniform": angle_result["fallback_uniform"],
            "angle_cumulative_deg": angle_result["report"]["cumulative_angle_deg"],
            "candidate_stats": {
                candidate["direction"]: candidate["stats"]
                for candidate in candidates
            },
        },
        "logs": {
            "feature_extractor": str(logs_dir / "colmap_feature_extractor.log"),
            "sequential_matcher": str(logs_dir / "colmap_sequential_matcher.log"),
            "model_analyzer": str(logs_dir / "colmap_model_analyzer.log"),
        },
    }
