# Videoto3D V1.4 Capture-Method Workflows Design

## Goal
Separate camera-moving/object-fixed capture and camera-fixed/object-rotating capture into peer workflows selected when a Run is created.

## Naming
Use only `orbit_camera` / Orbit Camera and `turntable` / Turntable. Do not introduce A/B labels.

## Orbit Camera
Stable full-RGB COLMAP incremental SfM. SAM2 does not constrain pose recovery. Preserve current Run/Viewer/GLB/PLY engineering improvements.

## Turntable
Research workflow. Freeze V1.3 constrained-pose implementation as `legacy_v13`. Future work follows turntable-constrained geometry, global orbit refinement, observability diagnostics and eventually SfM-free Gaussian reconstruction.

## Run lifecycle
Capture Method is selected in New Run together with video and Run ID and becomes immutable after source import/extraction.

## CLI
Canonical command entry is `python Videoto3D.py ...`. `app.py` remains internal compatibility code.

## Frontend
RunDetailPage routes by `capture_mode` to independent OrbitCameraRunView and TurntableRunView.

## Non-goals
V1.4 Phase 1 does not implement the new research pose solver or RotGS-like Gaussian optimizer. It establishes isolation and preserves the V1.3 baseline.
