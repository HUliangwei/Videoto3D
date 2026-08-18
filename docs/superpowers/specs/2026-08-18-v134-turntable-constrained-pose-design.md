# V1.3.4 Turntable-Constrained Pose Design

## Problem

Real Turntable runs can register every frame yet still produce weak sparse geometry and unusable downstream Mesh/Splat output. The `hlw_04` diagnostic showed that feature supply is not the first bottleneck: 28/37 adjacent pairs were verified, 54 temporal pairs were available, and the median verified-pair inlier count was 119. The dominant rotation axis was only 2.51 degrees from camera Y, but pairwise generic essential decompositions had a 30.81 degree median axis deviation.

The production weakness is therefore the conversion from verified two-view geometry into a one-dimensional Turntable angle. V1.3.3 decomposes each essential matrix as unconstrained 3-D motion and then keeps only the rotation magnitude. That gives the estimator degrees of freedom that the capture model does not physically have.

## Goal

Estimate each temporal pair angle directly under the existing Turntable motion model, while preserving the current free-span graph, CW/CCW candidate triangulation, and both downstream reconstruction routes.

## Motion Model

The existing known-pose backend is retained:

- fixed physical camera;
- rigid subject;
- dominant rotation axis aligned with camera Y;
- constant COLMAP translation vector `t`;
- one-directional motion over the selected clip;
- arbitrary angular speed and arbitrary total span.

For a signed pair angle `dtheta`:

```text
Rrel(dtheta) = Ry(dtheta)
trel(dtheta) = t - Rrel(dtheta) * t
Eturntable(dtheta) = [trel]x * Rrel
```

## Pair Estimation

V1.3.4 reads COLMAP's verified match indices from `two_view_geometries.data` and the corresponding keypoints from the `keypoints` table. SIMPLE_RADIAL points are undistorted into normalized camera coordinates. Candidate signed Turntable angles are scored with the median Sampson residual under `Eturntable(dtheta)`.

A coarse-to-fine one-dimensional search is used because each pair has only one rotational degree of freedom. The accepted graph edge stores the absolute angle magnitude; signed direction is retained for diagnostics. Existing CW/CCW known-pose triangulation continues to resolve the global virtual-camera direction.

Pairs whose median constrained-model residual exceeds 3 px are excluded from the production angle graph. Inlier count and model residual both contribute to graph weighting.

## Rotation Center Compatibility

The existing `pipeline.turntable.estimate_turntable_translation()` call boundary is not changed in this overlay. `turntable_angle.py` mirrors the same SAM2 mask-median estimate from the stable run layout `run_root/masks`. This allows the existing `estimate_adaptive_turntable_angles(database, images, camera, ...)` call to remain source-compatible while using the same physical center model. If mask files are unavailable, the principal axis `(tx, ty, tz) = (0, 0, 1)` is used only as a compatibility fallback.

## A/B Diagnostics

The report keeps legacy V1.3.3 generic-E results alongside the constrained estimator:

- `angle_estimator`;
- `legacy_total_span_deg`;
- `legacy_raw_increment_deg`;
- `constrained_valid_pairs`;
- `constrained_pair_coverage_ratio`;
- `median_model_residual_px`;
- `max_model_residual_px`;
- per-pair `legacy_angle_deg` vs `constrained_angle_deg`;
- model residual, matrix similarity, inliers, acceptance and rejection reason.

The existing keys consumed by the app remain available, including `strategy`, `total_span_deg`, `valid_pair_ratio`, `estimated_increment_deg`, `normalized_increment_deg`, and `cumulative_angle_deg`.

## Compatibility Fallback

Old/synthetic databases may contain F/E matrices but no usable verified-match blobs. If fewer than three constrained edges can be built, V1.3.4 falls back to the V1.3.3 generic essential-magnitude reader. It does not restore a forced 360-degree span.

## Explicit Non-Goals

V1.3.4 does not change:

- SAM2 segmentation;
- SIFT feature extraction;
- sequential matcher settings;
- frame extraction;
- free-span graph architecture;
- CW/CCW candidate selection;
- COLMAP `point_triangulator`;
- OpenMVS;
- Blender or GLB export;
- Brush, Splat cleanup, or PLY export;
- Studio or Viewer code.

## Validation

Synthetic tests must show that constrained fitting:

1. recovers a known Turntable angle under sub-pixel image noise;
2. handles COLMAP pair-ID ordering that differs from filename order;
3. recovers a non-uniform free-span trajectory from multi-baseline constraints;
4. continues to work when the stored generic essential rotation is deliberately misleading but verified correspondences are correct;
5. preserves the V1.3.3 generic fallback for databases without match blobs.

The real regression target remains `hlw_04`. After overlay, rerun only Sparse first and compare angle A/B diagnostics, sparse points, track length, and reprojection error before rerunning Mesh or Splat.
