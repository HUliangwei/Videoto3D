# V1.3.4.1 Turntable Pose A/B Benchmark Design

## Goal

Determine whether the V1.3.4 constrained Turntable angle trajectory produces a better COLMAP sparse model than the legacy generic-essential trajectory when both use the exact same `database.db`, frames, masks, camera model, known-pose triangulator, and CW/CCW candidate-selection rule.

## Scope

The benchmark is diagnostic only. It must not modify `workspace/runs/<run>/colmap/sparse/0`, the COLMAP database, frame extraction, SAM2, SIFT, sequential matching, OpenMVS, Blender, Brush, GLB, PLY, Viewer, or Studio.

All benchmark artifacts live under:

`workspace/runs/<run>/colmap/diagnostics/pose_ab_v1341/`

## Data Flow

For one existing run:

1. Read the existing `colmap/database.db`, shared camera, images, frames, and masks.
2. Estimate the same Turntable translation used by production known-pose reconstruction.
3. Build a legacy free-span trajectory from generic essential-matrix rotation constraints.
4. Build a constrained free-span trajectory from V1.3.4 one-axis correspondence fitting.
5. For each trajectory, generate CW and CCW known-pose models.
6. Run the existing COLMAP `point_triangulator` and `model_analyzer` on each candidate.
7. Select the best direction using the same production rule: points first, reprojection error second.
8. Write a JSON report containing spans, graph coverage, candidate metrics, selected metrics, and constrained-minus-legacy deltas.

## Success Criterion

The benchmark itself is successful when it produces a complete A/B report without changing shared `sparse/0`. The experiment favors constrained poses only if the same-database constrained model increases sparse points and/or track length without a material reprojection-error regression. If it does not, matching changes are deferred until the pose estimator is reconsidered.
