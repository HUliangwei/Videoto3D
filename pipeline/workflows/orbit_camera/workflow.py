"""Stable object-fixed / camera-moving workflow.

V1.4 intentionally preserves the validated Orbit Camera behavior:
full-RGB COLMAP incremental SfM. SAM2 masks are downstream object
constraints and never participate in Orbit Camera pose recovery.
"""

from pipeline.colmap import run_sparse_reconstruction

def run_sparse(*, colmap_path, frames_dir, masks_dir, colmap_dir, logs_dir, overwrite=True):
    reconstruction = run_sparse_reconstruction(
        colmap_path=colmap_path,
        frames_dir=frames_dir,
        colmap_dir=colmap_dir,
        logs_dir=logs_dir,
        overwrite=overwrite,
        mask_path=None,
    )
    return {
        "result": reconstruction,
        "pose_strategy": "incremental_sfm",
        "mask_guided": False,
        "details": {},
    }
