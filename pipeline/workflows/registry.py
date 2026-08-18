"""Capture-method workflow registry for Videoto3D V1.4."""

from __future__ import annotations
from dataclasses import dataclass
from importlib import import_module
from pipeline.capture_mode import normalize_capture_mode

@dataclass(frozen=True)
class CaptureWorkflowSpec:
    id: str
    label: str
    description: str
    maturity: str
    module: str

_WORKFLOWS = {
    "orbit_camera": CaptureWorkflowSpec(
        id="orbit_camera",
        label="Orbit Camera",
        description="Object fixed; camera moves around the object.",
        maturity="stable",
        module="pipeline.workflows.orbit_camera.workflow",
    ),
    "turntable": CaptureWorkflowSpec(
        id="turntable",
        label="Turntable",
        description="Camera fixed; rigid object rotates around one dominant axis.",
        maturity="research",
        module="pipeline.workflows.turntable.workflow",
    ),
}

def get_capture_workflow(value=None) -> CaptureWorkflowSpec:
    return _WORKFLOWS[normalize_capture_mode(value)]

def run_sparse_for_capture(value, **kwargs):
    spec = get_capture_workflow(value)
    module = import_module(spec.module)
    return module.run_sparse(**kwargs)
