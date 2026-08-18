"""Map R0.1 Blender ground truth into conventional CV camera coordinates."""
from __future__ import annotations
import numpy as np
from .single_axis import normalize_axis

_BLENDER_CAMERA_TO_CV = np.diag([1.0, -1.0, -1.0])

def camera_intrinsics_from_ground_truth(camera):
    if "intrinsics_px" in camera:
        k = np.asarray(camera["intrinsics_px"], dtype=np.float64)
        if k.shape != (3,3):
            raise ValueError("camera.intrinsics_px must be 3x3")
        return k
    width, height = [int(v) for v in camera["resolution"]]
    focal_mm = float(camera["focal_mm"])
    sensor_width_mm = float(camera["sensor_width_mm"])
    focal_px = focal_mm * float(width) / sensor_width_mm
    return np.array([
        [focal_px, 0.0, 0.5*width],
        [0.0, focal_px, 0.5*height],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

def shared_geometry_from_ground_truth(payload):
    camera = payload["camera"]
    matrix_world = np.asarray(camera["matrix_world"], dtype=np.float64)
    if matrix_world.shape != (4,4):
        raise ValueError("camera.matrix_world must be 4x4")
    r_cw = matrix_world[:3,:3]
    camera_center_world = matrix_world[:3,3]
    r_wc_cv = _BLENDER_CAMERA_TO_CV @ r_cw.T
    axis_world = np.asarray(payload["rotation_axis_world"], dtype=np.float64)
    center_world = np.asarray(payload["rotation_center_world"], dtype=np.float64)
    return {
        "intrinsics": camera_intrinsics_from_ground_truth(camera),
        "axis_cv": normalize_axis(r_wc_cv @ axis_world),
        "orbit_vector_cv": r_wc_cv @ (center_world - camera_center_world),
        "rotation_world_to_cv": r_wc_cv,
        "camera_center_world": camera_center_world,
    }

def ground_truth_delta_deg(payload, left_index, right_index):
    frames = payload["frames"]
    return float(frames[int(right_index)]["angle_deg"]) - float(frames[int(left_index)]["angle_deg"])
