# Turntable R0.1 Synthetic Benchmark Design

## Status
Approved research sub-project after Videoto3D V1.4.0.

## Goal
Create a deterministic ground-truth Turntable benchmark so future single-axis pose solvers are measured quantitatively before 3D reconstruction.

## Constraints
- Do not modify Orbit Camera.
- Do not modify `pipeline/workflows/turntable/legacy_v13/`.
- Do not modify OpenMVS, Brush, Blender export, GLB, or PLY routes.
- Generated benchmark data stays under `workspace/research/turntable/`.
- Real captures remain in `workspace/runs/<run_id>/`.
- Normal Python modules depend only on NumPy.
- Blender imports exist only inside the standalone rendering tool.

## Architecture
Pure-Python modules define structured single-axis motion, deterministic angle profiles and metrics. A Blender script imports GLB/GLTF, fixes the camera, rotates the rigid object around a world Z axis, renders frames and alpha-derived masks, and writes `ground_truth.json`.

## Non-goals
R0.1 does not estimate angles from images, optimize a global orbit, triangulate sparse points, run OpenMVS, or train Gaussian splats.
