# Turntable R0.4/R0.5 Fast GLB Route

## Milestone
This checkpoint intentionally prioritizes end-to-end wiring over final pose accuracy.

R0.4 solves a GT-free global orbit from R0.3c gap-2/gap-3 measurements plus residual-gated gap-5 measurements. On the current synthetic report the expected free-span solution is around 282.45 degrees with zero monotonicity violations; the remaining approximately 0.8 percent angular-scale bias is accepted for this milestone.

R0.5 follows COLMAP's documented known-pose workflow: extract features/matches into a database, manually construct `cameras.txt`, `images.txt`, and empty `points3D.txt` using database image IDs, then run `point_triangulator`.

After triangulation, the existing Videoto3D `pipeline.openmvs.run_mesh_pipeline` is reused unchanged. The resulting `object.obj` is exported through the existing Blender GLB exporter.

## Target artifact
`workspace/research/turntable/r05/<dataset>/output/turntable.glb`

## Deferred
- absolute angular-scale correction
- cycle-consistent research optimizer
- pose bundle refinement
- mesh quality tuning
- texture quality tuning
- real-capture calibration generalization
