# V1.3.2 Adaptive Turntable Angle Design

## Goal

Keep manual capture-mode selection and make Turntable tolerate non-uniform rotation speed without changing either downstream reconstruction route.

```text
Orbit Camera → existing incremental SfM → Mesh / Splat
Turntable    → adaptive per-frame angle → known poses → triangulation → Mesh / Splat
```

## Input contract

Turntable still assumes:
- fixed camera;
- rigid subject;
- approximately one complete 360° turn;
- mostly monotonic rotation direction;
- subject reasonably centered;
- camera approximately level.

Uniform speed is **not** required. Short speed-up/slow-down sections are allowed. Long reversals or repeated back-and-forth motion are out of scope.

## Angle source

COLMAP already performs mask-guided feature matching and geometric verification. V1.3.2 reuses `two_view_geometries` from `database.db`.

For adjacent image pair `(i,i+1)`:
1. read verified `E`; if unavailable, read `F` and compute `E=K^T F K`;
2. decompose `E=UΣV^T`;
3. form the two valid rotation candidates;
4. choose the smaller adjacent-frame rotation magnitude;
5. reject degenerate, near-zero, >60° and low-inlier pairs.

The COLMAP database contract stores `F/E/H` as row-major 3×3 float64 matrices.

## Robust angle trajectory

Raw adjacent increments can contain missing/outlier values. The estimator:
- fills missing values from the global median when enough verified pairs exist;
- replaces isolated local outliers using a median neighborhood;
- applies light local smoothing while retaining speed variation;
- normalizes the total angular span to `2π(N-1)/N`;
- cumulatively integrates positive increments to produce monotonic per-frame angles.

If fewer than 30% of adjacent pairs (minimum 3) provide valid geometry, the estimator safely falls back to the prior uniform-360 strategy.

## Reconstruction

The resulting angle vector is converted to known virtual camera poses. CW and CCW candidates are still triangulated, and sparse point count/reprojection error select the stronger candidate.

The selected model remains `colmap/sparse/0`; therefore OpenMVS, Brush, cleanup, Blender and both viewers remain unchanged.

## Diagnostics

Every Turntable run writes:

```text
colmap/turntable_angle_report.json
```

It records:
- raw adjacent angle estimates;
- normalized increments;
- cumulative angles;
- valid-pair ratio;
- adaptive/fallback strategy.

## Out of scope

- dynamic/4D human motion;
- turntable direction reversals;
- arbitrary camera motion during Turntable capture;
- metric scale;
- automatic capture-mode selection.
