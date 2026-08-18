"""Synthetic benchmark utilities for Turntable research."""
from .metrics import angle_sequence_metrics, axis_error_deg
from .profiles import AngleProfile, generate_profile
__all__ = ["AngleProfile", "angle_sequence_metrics", "axis_error_deg", "generate_profile"]
