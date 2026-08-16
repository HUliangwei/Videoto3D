# Videoto3D V0.9 Gaussian Splat Branch Design

## Status

Accepted by user on 2026-08-16. Public approach: generic `splat` CLI backed by a Brush adapter.

## Goal

Add Gaussian Splat PLY as a second output of each Multi-Run task without disturbing the verified OpenMVS → OBJ → GLB branch.

## Public CLI

```text
python app.py run splat --run <run_id> [--steps 30000] [--max-splats 2000000] [--max-resolution 1280]
python app.py view splat (--run <run_id> | --path <ply>)
```

The public interface intentionally says `splat`, not `brush`, so the backend can be replaced later.

## Data flow

```text
frames + masks + colmap/sparse/0
          ↓
brush/dataset staging
          ↓
Brush headless training
          ↓
brush/exports checkpoints
          ↓
output/<run_id>_splat.ply
```

Brush staging contains `images/`, `masks/`, and `sparse/0/`. RGB and SAM2 masks are hard-linked when possible and copied otherwise. Original Run data is never modified.

## Defaults

- 30000 training steps
- 2,000,000 maximum splats
- 1280 maximum image resolution
- export every 5000 steps

The first real-machine validation may use 10000 / 1,000,000 / 960 before the default-quality run.

## Manifest

Run schema v2 adds an independent `splat` stage. A Run may have GLB only, Splat only, or both. `complete` means both outputs are ready; otherwise status can be `glb_ready` or `splat_ready`.

## Viewer process model

All external GUI viewers (COLMAP, Blender, Brush) are launched detached. On Windows they use a detached process/new process group with inherited stdio disabled. This resolves BUG-0002 where closing a viewer could leave PowerShell requiring Ctrl+C.

## Non-goals

- No Gaussian Splat → mesh conversion in V0.9.
- No automatic Brush checkpoint resume in V0.9.
- No Web GUI in V0.9.
- No replacement of the OpenMVS branch.
