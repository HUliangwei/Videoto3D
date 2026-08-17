"""Capture-mode helpers for Videoto3D V1.3.

Orbit camera keeps the existing full-RGB SfM behavior. Turntable mode keeps the
camera physically fixed while a rigid subject rotates; COLMAP therefore uses
SAM2 masks as ImageReader feature masks so the static background cannot dominate
pose estimation.
"""

from pathlib import Path

DEFAULT_CAPTURE_MODE = "orbit_camera"
CAPTURE_MODES = ("orbit_camera", "turntable")
_CAPTURE_ALIASES = {
    "orbit": "orbit_camera",
    "orbit-camera": "orbit_camera",
    "orbit_camera": "orbit_camera",
    "camera-orbit": "orbit_camera",
    "camera_orbit": "orbit_camera",
    "turntable": "turntable",
    "turn-table": "turntable",
    "turn_table": "turntable",
}


def normalize_capture_mode(value=None):
    raw = DEFAULT_CAPTURE_MODE if value is None or str(value).strip() == "" else str(value).strip().lower()
    normalized = _CAPTURE_ALIASES.get(raw)
    if normalized is None:
        raise ValueError(
            "Unknown capture mode {!r}. Use orbit_camera or turntable.".format(value)
        )
    return normalized


def is_turntable(value):
    return normalize_capture_mode(value) == "turntable"


def sparse_mask_path(run_root, capture_mode):
    """Return COLMAP ImageReader.mask_path for this capture mode."""
    if not is_turntable(capture_mode):
        return None
    return Path(run_root) / "masks"


def capture_mode_label(value):
    mode = normalize_capture_mode(value)
    return "Turntable" if mode == "turntable" else "Orbit Camera"


def sparse_strategy_label(value):
    return "SAM2 mask-guided features" if is_turntable(value) else "Full RGB features"
