# Videoto3D V0.10 Dual Route Run Layout Design

## Goal

Keep each Run physically flat and readable while modeling progress logically as Shared stages plus Mesh and Splat routes. Add one-command route orchestration and remove Brush background clutter by filtering COLMAP initialization points against SAM2 masks without changing camera poses.

## Run layout

```text
workspace/runs/<run_id>/
├─ run.json
├─ source/
├─ frames/
├─ masks/
├─ segmentation/
├─ colmap/
├─ mesh/
│  ├─ mvs_colmap/
│  ├─ openmvs_masks/
│  ├─ openmvs/
│  └─ blender/
├─ splat/
│  ├─ dataset/
│  ├─ object_sparse_report.json
│  ├─ recipe.json
│  ├─ exports/
│  └─ legacy_v09/
├─ output/
└─ logs/
   ├─ shared/
   ├─ mesh/
   └─ splat/
```

Shared assets remain at the Run root. Only route-private intermediates live under `mesh/` and `splat/`. Final user-facing assets remain together in `output/`.

## Manifest schema v3

`run.json` separates logical progress from physical layout:

```json
{
  "shared": {
    "extract": {"status": "ready"},
    "mask": {"status": "ready"},
    "sparse": {"status": "ready"}
  },
  "routes": {
    "mesh": {
      "dense": {"status": "ready"},
      "reconstruct": {"status": "ready"},
      "refine": {"status": "ready"},
      "texture": {"status": "ready"},
      "glb": {"status": "ready"}
    },
    "splat": {
      "object_sparse": {"status": "ready"},
      "training": {"status": "ready"},
      "ply": {"status": "ready"}
    }
  }
}
```

V0.9 manifests/layouts migrate automatically and non-destructively. Existing V0.9 Brush outputs are preserved under `splat/legacy_v09/`; V0.10 marks the Splat route pending because it requires object-only initialization.

## Route commands

```text
python app.py route mesh --run <run_id> [--input <video>]
python app.py route splat --run <run_id> [--input <video>] [Brush/object-filter overrides]
```

Routes reuse existing ready shared stages. A new Run requires `--input`; an existing Run may omit it. Supplying `--input` refreshes the source and invalidates downstream work.

Fine-grained `run` and `view` commands remain available.

## Object-only Splat initialization

Use the full RGB COLMAP model for camera registration. Do not rerun masked SfM. Filter `points3D.bin` only:

1. Parse each 3D point track `(image_id, point2D_idx)`.
2. Resolve each observation to the corresponding `(x, y)` in `images.bin`.
3. Sample the existing SAM2 mask for that image.
4. Keep a 3D point when foreground observations >= 2 and foreground ratio >= 0.60 by default.
5. Preserve all cameras and images; write a consistent filtered `points3D.bin` and set removed point references in staged `images.bin` to `-1`.
6. Write `splat/object_sparse_report.json` with counts and thresholds.

`view splat-init` opens the staged object-only COLMAP model before expensive training.

## Progress

`runs list` displays three columns: Shared, Mesh Route, Splat Route. `runs show` expands detailed sub-stage status and key metrics. File-derived progress supplements the manifest so partially completed OpenMVS/Brush work remains visible after failures.

## Compatibility

V0.7.3 OpenMVS TextureMesh workaround remains unchanged. Viewer processes remain detached. README is the canonical command reference and must include every canonical command.
