# Turntable Engineering Workflow

## User-facing route

```powershell
python Videoto3D.py route mesh --run <run_id>
```

`route mesh` reads `workspace/runs/<run_id>/run.json`.

For `orbit_camera`, the existing full-RGB incremental COLMAP SfM path is unchanged.

For `turntable`, `run sparse` expands internally to:

```text
anchor
  -> pairs
  -> orbit
  -> known-pose triangulate
  -> colmap/sparse/0
```

After `colmap/sparse/0`, both capture methods share the same OpenMVS Mesh route and Blender GLB export.

## Debug commands

```powershell
python Videoto3D.py run anchor --run <run_id>
python Videoto3D.py run pairs --run <run_id>
python Videoto3D.py run orbit --run <run_id>
python Videoto3D.py run triangulate --run <run_id>
```

The shared commands remain:

```powershell
python Videoto3D.py run sparse --run <run_id>
python Videoto3D.py run mesh --run <run_id>
python Videoto3D.py run glb --run <run_id>
python Videoto3D.py view glb --run <run_id>
```

## Run workspace

All Turntable runtime data lives inside:

```text
workspace/runs/<run_id>/
├─ run.json
├─ frames/
├─ masks/
├─ turntable/
│  ├─ calibration.json
│  ├─ observations/
│  │  ├─ graph.json
│  │  └─ graph.npz
│  ├─ anchor.json
│  ├─ pairs.json
│  ├─ orbit.json
│  ├─ image_list.txt
│  └─ feature_masks/
├─ colmap/
│  ├─ database.db
│  ├─ known_pose/
│  └─ sparse/0/
├─ mesh/
├─ output/
└─ logs/
```

External tools provide executables only; Run data is never written to their installation directories.

## Current engineering compromise

The structured Turntable pose and global angle sequence remain GT-free. For real-video intrinsics, this milestone bootstraps camera intrinsics from the frozen V1.3 Turntable COLMAP reconstruction. The bootstrap poses are not used by the new structured orbit.

A dedicated calibration stage can replace this later without changing the public CLI or downstream Mesh/GLB contract.
