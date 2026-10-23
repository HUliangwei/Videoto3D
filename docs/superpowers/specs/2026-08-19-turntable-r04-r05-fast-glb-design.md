# Turntable R0.4/R0.5 Fast GLB Route Design

## Goal
Prioritize a first end-to-end Turntable GLB over final pose accuracy. Build a stable GT-free global orbit from the R0.3c pair measurements, convert it into known COLMAP camera poses, triangulate a sparse model with COLMAP, reuse the existing OpenMVS mesh pipeline, and export the textured OBJ to GLB with the existing Blender exporter.

## R0.4 Global Orbit
Use R0.3c top-1 pair measurements from gaps 2 and 3 as the primary graph. Gap-5 measurements are optional and automatically gated by pair Sampson residual. Solve positive adjacent increments with weighted least squares plus Huber IRLS. Fix theta_0=0; do not impose 280 or 360 degrees.

The expected synthetic span bias of roughly 0.8 percent is explicitly accepted for this engineering milestone.

## R0.5 Known-Pose Geometry Route
1. Read synthetic calibration and frame names from the dataset.
2. Extract SIFT into a fresh R0.5 COLMAP database using one shared PINHOLE camera with known `fx,fy,cx,cy`.
3. Sequentially match the video frames.
4. Query actual image IDs and camera ID from the database.
5. Write a manual COLMAP text model:
   - `cameras.txt`
   - `images.txt`
   - empty `points3D.txt`
   `rigs.txt` and `frames.txt` are omitted intentionally because COLMAP 4.x remains backward compatible and initializes trivial rigs/frames.
6. Absolute virtual-camera pose at angle theta:
   - R(theta) = axis-angle rotation around the recovered shared axis
   - t(theta) = u - R(theta) u
   where u is the unit transverse orbit direction. Global scale is arbitrary and fixed to 1.
7. Run COLMAP `point_triangulator` against the feature database.
8. Hand the triangulated sparse model to the existing `pipeline.openmvs.run_mesh_pipeline`.
9. Export OpenMVS `object.obj` through existing `pipeline.blender.export_obj_to_glb` and `scripts/blender_export_glb.py`.

## Fast-path defaults
- gaps: 2,3 plus gated sparse 5
- gap5 residual threshold: max(0.5 px, 4 * median gap2/3 residual)
- sequential matching overlap: 8
- no global bundle adjustment before OpenMVS
- OpenMVS existing default mesh profile
- no pose optimization after triangulation

## Success criterion
Create a non-empty GLB in:
`workspace/research/turntable/r05/<dataset-name>/output/turntable.glb`

This milestone proves the wiring. Geometry/texture quality and the remaining absolute angular-scale bias are deferred.
