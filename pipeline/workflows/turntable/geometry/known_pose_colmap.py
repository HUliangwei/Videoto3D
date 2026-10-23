"""COLMAP known-pose helpers for Turntable R0.5."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
import numpy as np

from pipeline.workflows.turntable.pose.single_axis import axis_angle_rotation, normalize_axis


def virtual_camera_pose(axis, transverse_direction, angle_deg):
    """Absolute world-to-camera pose in the virtual-camera gauge."""
    axis = normalize_axis(axis)
    u = np.asarray(transverse_direction, dtype=np.float64)
    u = u - axis * float(axis @ u)
    norm = float(np.linalg.norm(u))
    if norm <= 1e-12:
        raise ValueError("transverse_direction is parallel to axis")
    u = u / norm

    rotation = axis_angle_rotation(axis, math.radians(float(angle_deg)))
    translation = u - rotation @ u
    return rotation, translation


def relative_pose(r1, t1, r2, t2):
    r1 = np.asarray(r1, dtype=np.float64)
    r2 = np.asarray(r2, dtype=np.float64)
    t1 = np.asarray(t1, dtype=np.float64)
    t2 = np.asarray(t2, dtype=np.float64)
    relative_rotation = r2 @ r1.T
    relative_translation = t2 - relative_rotation @ t1
    return relative_rotation, relative_translation


def matrix_to_qvec(rotation):
    """Convert 3x3 rotation matrix to COLMAP qw,qx,qy,qz."""
    r = np.asarray(rotation, dtype=np.float64)
    if r.shape != (3, 3):
        raise ValueError("rotation must be 3x3")

    trace = float(np.trace(r))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (r[2, 1] - r[1, 2]) / s
        qy = (r[0, 2] - r[2, 0]) / s
        qz = (r[1, 0] - r[0, 1]) / s
    else:
        diag = np.diag(r)
        index = int(np.argmax(diag))
        if index == 0:
            s = math.sqrt(max(1e-15, 1.0 + r[0, 0] - r[1, 1] - r[2, 2])) * 2.0
            qw = (r[2, 1] - r[1, 2]) / s
            qx = 0.25 * s
            qy = (r[0, 1] + r[1, 0]) / s
            qz = (r[0, 2] + r[2, 0]) / s
        elif index == 1:
            s = math.sqrt(max(1e-15, 1.0 + r[1, 1] - r[0, 0] - r[2, 2])) * 2.0
            qw = (r[0, 2] - r[2, 0]) / s
            qx = (r[0, 1] + r[1, 0]) / s
            qy = 0.25 * s
            qz = (r[1, 2] + r[2, 1]) / s
        else:
            s = math.sqrt(max(1e-15, 1.0 + r[2, 2] - r[0, 0] - r[1, 1])) * 2.0
            qw = (r[1, 0] - r[0, 1]) / s
            qx = (r[0, 2] + r[2, 0]) / s
            qy = (r[1, 2] + r[2, 1]) / s
            qz = 0.25 * s

    q = np.asarray([qw, qx, qy, qz], dtype=np.float64)
    q /= float(np.linalg.norm(q))
    if q[0] < 0.0:
        q = -q
    return q


def database_image_map(database_path):
    con = sqlite3.connect(str(Path(database_path)))
    try:
        rows = con.execute(
            "SELECT image_id, name, camera_id FROM images"
        ).fetchall()
    finally:
        con.close()
    return {
        str(name).replace("\\", "/"): {
            "image_id": int(image_id),
            "camera_id": int(camera_id),
        }
        for image_id, name, camera_id in rows
    }


def write_known_pose_text_model(
    database_path,
    output_dir,
    image_names,
    angles_deg,
    axis,
    transverse_direction,
    intrinsics,
    width,
    height,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_names = [str(name).replace("\\", "/") for name in image_names]
    angles_deg = list(angles_deg)
    if len(image_names) != len(angles_deg):
        raise ValueError("image_names and angles_deg length mismatch")

    mapping = database_image_map(database_path)
    missing = [name for name in image_names if name not in mapping]
    if missing:
        raise RuntimeError(
            "COLMAP database is missing images: {}".format(missing[:5])
        )

    camera_ids = {mapping[name]["camera_id"] for name in image_names}
    if len(camera_ids) != 1:
        raise RuntimeError("R0.5 fast route expects one shared camera")
    camera_id = int(next(iter(camera_ids)))

    k = np.asarray(intrinsics, dtype=np.float64)
    fx, fy, cx, cy = (
        float(k[0, 0]),
        float(k[1, 1]),
        float(k[0, 2]),
        float(k[1, 2]),
    )
    camera_line = "{} PINHOLE {} {} {:.15g} {:.15g} {:.15g} {:.15g}\n".format(
        camera_id, int(width), int(height), fx, fy, cx, cy
    )
    (output_dir / "cameras.txt").write_text(camera_line, encoding="utf-8")

    lines = []
    pose_records = []
    for name, angle in zip(image_names, angles_deg):
        entry = mapping[name]
        rotation, translation = virtual_camera_pose(
            axis,
            transverse_direction,
            float(angle),
        )
        q = matrix_to_qvec(rotation)
        line = (
            "{} {:.17g} {:.17g} {:.17g} {:.17g} "
            "{:.17g} {:.17g} {:.17g} {} {}"
        ).format(
            entry["image_id"],
            q[0], q[1], q[2], q[3],
            translation[0], translation[1], translation[2],
            camera_id,
            name,
        )
        lines.extend([line, ""])
        pose_records.append({
            "image_id": int(entry["image_id"]),
            "camera_id": camera_id,
            "name": name,
            "angle_deg": float(angle),
            "qvec": [float(v) for v in q],
            "tvec": [float(v) for v in translation],
        })

    (output_dir / "images.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    (output_dir / "points3D.txt").write_text("", encoding="utf-8")
    return {
        "camera_id": camera_id,
        "image_count": len(image_names),
        "poses": pose_records,
        "model_dir": str(output_dir),
    }


def feature_extractor_args(
    database_path,
    image_path,
    image_list_path,
    intrinsics,
    mask_path=None,
):
    k = np.asarray(intrinsics, dtype=np.float64)
    params = "{:.15g},{:.15g},{:.15g},{:.15g}".format(
        float(k[0,0]), float(k[1,1]), float(k[0,2]), float(k[1,2])
    )
    args = [
        "feature_extractor",
        "--database_path", str(Path(database_path)),
        "--image_path", str(Path(image_path)),
        "--image_list_path", str(Path(image_list_path)),
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", "PINHOLE",
        "--ImageReader.camera_params", params,
    ]
    if mask_path is not None:
        args += ["--ImageReader.mask_path", str(Path(mask_path))]
    return args


def sequential_matcher_args(database_path, overlap=8):
    return [
        "sequential_matcher",
        "--database_path", str(Path(database_path)),
        "--SequentialMatching.overlap", str(int(overlap)),
        "--SequentialMatching.loop_detection", "0",
    ]


def point_triangulator_args(database_path, image_path, input_path, output_path):
    return [
        "point_triangulator",
        "--database_path", str(Path(database_path)),
        "--image_path", str(Path(image_path)),
        "--input_path", str(Path(input_path)),
        "--output_path", str(Path(output_path)),
    ]
