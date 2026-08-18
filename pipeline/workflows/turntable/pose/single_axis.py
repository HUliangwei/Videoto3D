"""Single-axis geometry primitives for Turntable research.

Paper-derived premise:
- all views share one rotation axis;
- per-view motion is primarily parameterized by a rotation angle;
- translation is coupled to rotation through a shared orbit vector;
- the essential matrices therefore lie in a structured low-dimensional family.

This module is a deterministic motion model, not yet an image estimator.
"""
from __future__ import annotations
import math
from typing import Iterable, Tuple
import numpy as np

_EPS = 1e-12

def _vector3(value: Iterable[float], name: str) -> np.ndarray:
    vector = np.asarray(tuple(float(v) for v in value), dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain three finite values.")
    return vector

def normalize_axis(axis: Iterable[float]) -> np.ndarray:
    vector = _vector3(axis, "axis")
    norm = float(np.linalg.norm(vector))
    if norm <= _EPS:
        raise ValueError("axis must be non-zero.")
    return vector / norm

def skew(vector: Iterable[float]) -> np.ndarray:
    x, y, z = _vector3(vector, "vector")
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)

def axis_angle_rotation(axis: Iterable[float], angle_rad: float) -> np.ndarray:
    unit = normalize_axis(axis)
    angle = float(angle_rad)
    if not math.isfinite(angle):
        raise ValueError("angle_rad must be finite.")
    k = skew(unit)
    s, c = math.sin(angle), math.cos(angle)
    return np.eye(3, dtype=np.float64) + s * k + (1.0 - c) * (k @ k)

def structured_relative_pose(
    axis: Iterable[float],
    orbit_vector: Iterable[float],
    delta_angle_rad: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return R_ij and t_ij with t_ij = v - R_ij @ v."""
    rotation = axis_angle_rotation(axis, delta_angle_rad)
    orbit = _vector3(orbit_vector, "orbit_vector")
    translation = orbit - rotation @ orbit
    return rotation, translation

def structured_essential_matrix(
    axis: Iterable[float],
    orbit_vector: Iterable[float],
    delta_angle_rad: float,
) -> np.ndarray:
    rotation, translation = structured_relative_pose(axis, orbit_vector, delta_angle_rad)
    if float(np.linalg.norm(translation)) <= _EPS:
        raise ValueError("Structured essential matrix is degenerate for this angle/orbit.")
    essential = skew(translation) @ rotation
    if not np.all(np.isfinite(essential)):
        raise RuntimeError("Structured essential matrix contains non-finite values.")
    return essential
