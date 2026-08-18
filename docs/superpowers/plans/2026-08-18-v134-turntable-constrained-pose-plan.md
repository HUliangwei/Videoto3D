# V1.3.4 Turntable-Constrained Pose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace production generic essential-matrix angle extraction with one-degree-of-freedom Turntable-constrained fitting over verified COLMAP correspondences.

**Architecture:** Keep the V1.3.3 free-span graph and known-pose triangulation unchanged. Build each temporal edge by fitting verified keypoint correspondences to the existing constant-translation Y-axis orbit essential model, retain legacy E decomposition only for A/B diagnostics and compatibility fallback.

**Tech Stack:** Python 3.11+, NumPy, SQLite, Pillow, COLMAP database schema, pytest.

## Global Constraints

- Do not force total rotation to 360 degrees.
- Do not change OpenMVS, Blender, Brush, GLB, or PLY routes.
- Do not change Viewer or Studio code.
- Do not change Turntable feature-extractor or sequential-matcher settings in this iteration.
- Preserve existing public report keys used by app/run metadata consumers.

---

### Task 1: Constrained pair-angle fitter

**Files:**
- Modify: `pipeline/turntable_angle.py`
- Test: `tests/test_turntable_constrained_geometry_v134.py`

**Interfaces:**
- Produces: `turntable_essential_matrix(angle_rad, tvec)`
- Produces: `fit_turntable_rotation_from_correspondences(left_points_px, right_points_px, camera, tvec, max_angle_deg=120.0, min_angle_deg=0.05)`

- [x] Write a failing synthetic test that projects a rigid point cloud through two known Y-axis orbit poses with radial distortion and pixel noise.
- [x] Run the test and verify import failure because the constrained fitter does not exist.
- [x] Implement SIMPLE_RADIAL undistortion, Turntable essential construction, Sampson scoring, and coarse-to-fine signed angle search.
- [x] Verify the fitted angle is within 0.25 degrees and median residual is sub-pixel.

### Task 2: COLMAP verified-correspondence reader

**Files:**
- Modify: `pipeline/turntable_angle.py`
- Test: `tests/test_turntable_constrained_geometry_v134.py`

**Interfaces:**
- Produces: `read_turntable_constrained_constraints(...) -> {constraints, comparisons}`

- [x] Write a database test with non-monotonic COLMAP image IDs and per-image keypoint permutations.
- [x] Decode `keypoints.data` as float32 and `two_view_geometries.data` as uint32 match pairs.
- [x] Reorient match columns when canonical COLMAP ID order differs from filename order.
- [x] Fit signed angle for each temporal pair and retain only pairs below the model-residual threshold.
- [x] Store legacy angle, constrained angle, direction, residual and model similarity for A/B reporting.

### Task 3: Production free-span integration

**Files:**
- Modify: `pipeline/turntable_angle.py`
- Modify: `tests/test_turntable_adaptive_angle.py`
- Test: `tests/test_turntable_constrained_geometry_v134.py`

**Interfaces:**
- Preserves: `estimate_adaptive_turntable_angles(...)`
- Preserves: `angles_rad`, `increments_rad`, `valid_ratio`, `fallback_uniform`, and existing report keys.

- [x] Add optional `tvec` without breaking existing callers.
- [x] Mirror the existing SAM2 mask-center estimate when `tvec` is omitted.
- [x] Prefer constrained edges when at least three are available; otherwise use the legacy generic-E reader.
- [x] Weight constrained edges by inlier strength and constrained-model residual.
- [x] Add A/B report fields while preserving V1.3.3 report compatibility.
- [x] Verify non-uniform synthetic free-span recovery.
- [x] Verify deliberately misleading stored E rotations do not override correct correspondence-based angles.
- [x] Verify old tests without match blobs select `legacy_generic_essential_fallback`.

### Task 4: Verification and overlay packaging

**Files:**
- Create: `docs/superpowers/specs/2026-08-18-v134-turntable-constrained-pose-design.md`
- Create: `docs/superpowers/plans/2026-08-18-v134-turntable-constrained-pose-plan.md`

- [x] Run focused Turntable tests.
- [x] Run Python compilation checks.
- [x] Run a 38-frame synthetic stress case with mixed 1/2/4-frame baselines.
- [x] Check LF line endings and trailing whitespace.
- [x] Build an incremental overlay ZIP that does not include downstream reconstruction or Viewer files.
- [x] Verify ZIP integrity and compute SHA256.
