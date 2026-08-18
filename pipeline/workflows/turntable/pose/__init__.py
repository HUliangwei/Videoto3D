"""Turntable pose research primitives for Videoto3D."""
from .single_axis import (
    axis_angle_rotation,
    normalize_axis,
    structured_essential_matrix,
    structured_relative_pose,
)
from .structured_fit import (
    fit_structured_angle,
    normalized_homogeneous,
    sampson_squared,
    structured_angle_residual_px,
)
from .synthetic_geometry import (
    camera_intrinsics_from_ground_truth,
    ground_truth_delta_deg,
    shared_geometry_from_ground_truth,
)
from .shared_geometry import (
    directed_angle_error_deg,
    estimate_shared_geometry,
    line_angle_error_deg,
    observable_geometry_frame,
    observable_transverse_orbit,
    prepare_shared_geometry_pair,
    shared_geometry_objective_px,
)

__all__ = [
    "axis_angle_rotation",
    "normalize_axis",
    "structured_essential_matrix",
    "structured_relative_pose",
    "fit_structured_angle",
    "normalized_homogeneous",
    "sampson_squared",
    "structured_angle_residual_px",
    "camera_intrinsics_from_ground_truth",
    "ground_truth_delta_deg",
    "shared_geometry_from_ground_truth",
    "directed_angle_error_deg",
    "estimate_shared_geometry",
    "line_angle_error_deg",
    "observable_geometry_frame",
    "observable_transverse_orbit",
    "prepare_shared_geometry_pair",
    "shared_geometry_objective_px",
]
