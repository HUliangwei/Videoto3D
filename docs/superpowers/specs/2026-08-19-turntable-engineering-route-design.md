# Turntable Engineering Route Design

## Goal
Promote the validated Turntable geometry path into the canonical Videoto3D CLI without exposing research version numbers to normal users.

## CLI
The final user interface remains:
`python Videoto3D.py route mesh --run <run_id>`

The Run's immutable `capture_mode` in `workspace/runs/<run_id>/run.json` selects the sparse strategy automatically.

Public shared commands remain unchanged:
- `run sparse`
- `run mesh`
- `run glb`
- `view glb`

Turntable-only debug stages use the same canonical grammar:
- `run anchor`
- `run pairs`
- `run orbit`
- `run triangulate`

No `-turntable` suffix is added while those names are unambiguous.

## Workspace contract
Every input copy, intermediate product, cache, log, sparse model, mesh, texture and final GLB produced by a Run must remain below:
`workspace/runs/<run_id>/`

External COLMAP/OpenMVS/Blender/Brush locations are executable/runtime providers only.

## Routing
For `orbit_camera`, `run sparse` preserves the existing stable full-RGB incremental SfM path.

For `turntable`, `run sparse` orchestrates:
anchor -> pairs -> orbit -> known-pose triangulate

Both routes terminate at:
`workspace/runs/<run_id>/colmap/sparse/0`

Therefore the existing `run mesh`, `run glb`, and `view glb` remain shared.

## Turntable stage outputs
`workspace/runs/<run_id>/turntable/`
- `calibration.json`
- `observations/graph.json`
- `observations/graph.npz`
- `anchor.json`
- `pairs.json`
- `orbit.json`
- `image_list.txt`
- `feature_masks/`

Canonical COLMAP output:
`workspace/runs/<run_id>/colmap/`
- `database.db`
- `known_pose/`
- `sparse/0/`

## Calibration bootstrap
For this engineering milestone, Turntable intrinsics are bootstrapped from the frozen V1.3 Turntable reconstruction, but its poses are not used by the new structured orbit. This keeps the current validated route runnable before a dedicated real-video intrinsic-calibration stage is added.

## Invalidation
Re-running:
- anchor invalidates pairs/orbit/triangulate/mesh/glb
- pairs invalidates orbit/triangulate/mesh/glb
- orbit invalidates triangulate/mesh/glb
- triangulate invalidates mesh/glb

Changing extraction or masks invalidates the whole Turntable subtree.

## Non-goals
- no quality optimization
- no angular-scale correction
- no new GUI controls
- no changes to Orbit Camera math
- no changes to production OpenMVS/Blender code
