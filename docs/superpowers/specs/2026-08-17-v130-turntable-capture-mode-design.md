# V1.3.0 Turntable Capture Mode Design

## Goal

Support two explicit capture geometries without regressing V1.2 Orbit Camera behavior:

- `orbit_camera`: object stationary, camera moves; full-RGB Shared SfM.
- `turntable`: camera stationary, rigid object rotates; SAM2 mask-guided Shared SfM.

## Run contract

Top-level `run.json` field:

```json
{"capture_mode":"orbit_camera"}
```

Missing legacy values normalize to `orbit_camera`. The field is persistent for the Run.

## Pipeline behavior

`pipeline/capture_mode.py` owns normalization and mode labels. `pipeline/colmap.py` already exposes `mask_path` to `ImageReader.mask_path`, so V1.3 does not duplicate COLMAP execution logic.

`app.py::run_sparse` chooses:

```text
orbit_camera → mask_path=None
turntable    → mask_path=<run>/masks
```

Turntable requires a complete SAM2 mask set. Mask regeneration invalidates COLMAP sparse only in Turntable mode.

## GUI

New Run exposes a Capture Mode selector. Upload forwards `capture_mode` through the FastAPI query to the existing core CLI job. Run detail displays the persisted mode. No capture logic is implemented in React.

## Artifact / quality

Shared Artifact Inspector adds `Camera Trajectory`, implemented as a generic browser point cloud of COLMAP camera centers. Quality report adds capture mode and sparse feature strategy.

## Compatibility

Orbit Camera remains default and behavior-compatible with existing Runs. Existing V1.2 manifests do not require a destructive schema migration.

## Non-goals

- dynamic humans / articulated subjects
- 4D Gaussian Splatting
- SMPL / avatar fitting
- automatic turntable angle calibration
- replacing COLMAP with a learned pose model
