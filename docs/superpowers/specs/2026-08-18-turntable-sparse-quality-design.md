# Videoto3D V1.3.4 Turntable Sparse Quality Design

## Goal

Determine whether the failed Turntable Mesh/GLB and Splat/PLY outputs are primarily caused by the current hard-coded camera-Y rotation axis, weak foreground feature/match coverage, or both, before changing reconstruction behavior.

## Constraints

- Keep the existing Free-span angle model; do not reintroduce a forced 360-degree span.
- Do not change OpenMVS, Blender, Brush, GLB, PLY, or Splat route behavior during diagnosis.
- Keep all run data inside `workspace/runs/<run_id>`.
- Diagnosis must be read-only with respect to the COLMAP database and sparse model.
- Use the same SAM2 mask-guided foreground database already produced by Turntable sparse reconstruction.

## Root-cause hypotheses

1. **Rotation-axis model mismatch.** `pipeline/turntable.py` currently constructs all known-pose quaternions around camera Y. For a fixed camera that is pitched/rolled relative to the physical turntable, the equivalent virtual-camera rotation axis in camera coordinates is not exactly Y. The verified essential matrices contain relative rotation matrices from which this axis line can be estimated.
2. **Weak foreground view graph.** The observed sparse models have low point counts and short tracks. The current SIFT/matching settings may provide insufficient verified correspondences for a texture-poor rotating object.

## Diagnostic design

Add a standalone read-only tool `tools/turntable_diagnose_v134.py` that reads:

- shared SIMPLE_RADIAL intrinsics;
- per-image keypoint counts;
- verified `two_view_geometries`;
- E matrices, with F→E fallback;
- filename-order temporal gaps.

For each usable temporal pair, decompose E and select the smaller-angle proper rotation. Recover the unsigned axis line from the rotation matrix. Aggregate axis lines using the principal eigenvector of a weighted outer-product scatter matrix, which is invariant to axis sign.

The JSON report records:

- foreground keypoint min/median/max/total;
- adjacent verified pair ratio;
- temporal gap coverage;
- verified pairs by temporal gap;
- dominant rotation axis in camera coordinates;
- median/max axis deviation;
- angle between dominant axis and camera Y;
- concise diagnostic findings.

## Decision thresholds

- `axis_vs_camera_y_deg > 8°`: treat hard-coded Y as a likely pose-model error.
- `median_axis_deviation_deg > 10°`: pair rotations are too inconsistent to trust a single-axis estimate without further matching cleanup.
- `gap_coverage_ratio < 65%`: matching/view-graph coverage is weak.
- `median foreground keypoints < 500`: foreground SIFT density is weak.

These are diagnostic thresholds, not reconstruction hard gates.

## Next implementation decision

- If axis mismatch is clear and axis consistency is good: V1.3.4 production patch will build known poses around the recovered dominant axis, with camera-Y fallback when confidence is insufficient.
- If feature/match coverage is the dominant problem: V1.3.4 production patch will strengthen Turntable-only SIFT/matching while preserving the same known-pose triangulation and downstream routes.
- If both are present: implement axis recovery first, validate Sparse, then strengthen matching in a second isolated change.
