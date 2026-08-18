"""Camera-fixed / object-rotating research workflow for Videoto3D V1.4.

Phase 1 keeps the frozen V1.3 constrained-pose implementation only as a
research baseline. Structured-essential, global-orbit, cycle-consistency and
future SfM-free Gaussian work belongs under this workflow and must not modify
Orbit Camera reconstruction.
"""

from pipeline.segmentation import validate_masks
from pipeline.workflows.turntable.legacy_v13.reconstruction import run_turntable_reconstruction

def run_sparse(*, colmap_path, frames_dir, masks_dir, colmap_dir, logs_dir, overwrite=True):
    validate_masks(frames_dir, masks_dir)
    reconstruction = run_turntable_reconstruction(
        colmap_path=colmap_path,
        frames_dir=frames_dir,
        masks_dir=masks_dir,
        colmap_dir=colmap_dir,
        logs_dir=logs_dir,
        overwrite=overwrite,
    )
    details = reconstruction.get("turntable", {})
    return {
        "result": reconstruction,
        "pose_strategy": details.get("pose_strategy", "turntable_legacy_v13"),
        "mask_guided": True,
        "details": details,
    }
