"""Deterministic ground-truth angle profiles for Turntable benchmarks."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class AngleProfile:
    name: str
    angles_deg: np.ndarray
    description: str

    @property
    def frame_count(self) -> int:
        return int(len(self.angles_deg))

    @property
    def span_deg(self) -> float:
        return float(self.angles_deg[-1] - self.angles_deg[0]) if len(self.angles_deg) else 0.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "frame_count": self.frame_count,
            "span_deg": self.span_deg,
            "description": self.description,
            "angles_deg": [float(v) for v in self.angles_deg],
        }

def _validate_frame_count(frame_count: int) -> int:
    value = int(frame_count)
    if value < 3:
        raise ValueError("frame_count must be at least 3.")
    return value

def _nonuniform_angles(frame_count: int, span_deg: float) -> np.ndarray:
    n = _validate_frame_count(frame_count)
    steps = n - 1
    phase = np.linspace(0.0, 2.0 * np.pi, steps, endpoint=False)
    weights = 1.0 + 0.55 * np.sin(phase + 0.35) + 0.22 * np.sin(2.0 * phase + 1.1)
    weights = np.maximum(weights, 0.08)
    increments = float(span_deg) * weights / float(np.sum(weights))
    angles = np.concatenate(([0.0], np.cumsum(increments)))
    angles[-1] = float(span_deg)
    return angles.astype(np.float64)

def generate_profile(name: str, frame_count: int = 60) -> AngleProfile:
    key = str(name).strip().lower()
    n = _validate_frame_count(frame_count)
    if key == "uniform_360":
        angles = np.linspace(0.0, 360.0, n, dtype=np.float64)
        description = "Uniform full-turn control sequence."
    elif key == "nonuniform_360":
        angles = _nonuniform_angles(n, 360.0)
        description = "Variable-speed full-turn sequence."
    elif key == "nonuniform_280":
        angles = _nonuniform_angles(n, 280.0)
        description = "Variable-speed free-span 280-degree sequence."
    else:
        raise ValueError(
            "Unknown profile {!r}. Use uniform_360, nonuniform_360, or nonuniform_280.".format(name)
        )
    return AngleProfile(key, angles, description)
