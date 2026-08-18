# V1.3.4 Turntable Sparse Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Diagnose and then fix the Shared Sparse quality bottleneck causing failed Turntable GLB and PLY reconstruction.

**Architecture:** First add a read-only COLMAP database diagnostic that separates rotation-axis mismatch from weak feature/match coverage. Production reconstruction remains untouched until a real failed run such as `hlw_04` supplies the diagnostic evidence. The first production change will address only the dominant root cause, followed by another Sparse comparison before any downstream route tuning.

**Tech Stack:** Python 3.11, SQLite, NumPy, COLMAP 4.1.x database schema, pytest.

## Global Constraints

- Do not force Turntable span to 360 degrees.
- Do not modify OpenMVS, Blender, Brush, GLB, PLY, or Splat route behavior.
- Diagnosis is read-only and writes only `workspace/runs/<run_id>/colmap/turntable_diagnostic_v134.json`.
- Preserve the existing known-pose `point_triangulator` backend until diagnostic evidence requires a pose-model correction.

---

### Task 1: Read-only Turntable diagnostic

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/turntable_diagnose_v134.py`
- Test: `tests/test_turntable_diagnose_v134.py`

**Interfaces:**
- Consumes: `workspace/runs/<run_id>/colmap/database.db`
- Produces: `diagnose_database(database_path, min_inliers=12, max_gap=10) -> dict`
- Produces: `diagnose_run(project_root, run_id, output_path=None) -> (dict, Path)`

- [x] **Step 1: Write failing tests for axis-line recovery, sign-invariant dominant-axis aggregation, and synthetic database diagnosis.**
- [x] **Step 2: Run the focused tests and confirm they fail before implementation.**
- [x] **Step 3: Implement the minimal read-only diagnostic.**
- [x] **Step 4: Run `PYTHONPATH=. python -m pytest tests/test_turntable_diagnose_v134.py -q`.**

Expected: `3 passed`.

### Task 2: Diagnose the real failed Turntable run

**Files:**
- Read: `workspace/runs/hlw_04/colmap/database.db`
- Create at runtime: `workspace/runs/hlw_04/colmap/turntable_diagnostic_v134.json`

- [ ] **Step 1: Run:**

```powershell
python tools/turntable_diagnose_v134.py --run hlw_04
```

- [ ] **Step 2: Record these fields:**

```text
keypoints.median
geometry.adjacent_valid_ratio
geometry.gap_coverage_ratio
rotation_axis.axis_xyz
rotation_axis.axis_vs_camera_y_deg
rotation_axis.median_deviation_deg
findings
```

- [ ] **Step 3: Select exactly one first production hypothesis:**
  - axis mismatch when `axis_vs_camera_y_deg > 8` and median axis deviation is <=10°;
  - weak matching when coverage is <65% and axis mismatch is <=8°;
  - axis mismatch first when both conditions hold.

### Task 3A: Production axis recovery, only if Task 2 supports it

**Files:**
- Modify: `pipeline/turntable_angle.py`
- Modify: `pipeline/turntable.py`
- Modify: `tests/test_turntable_adaptive_angle.py`
- Modify: `tests/test_turntable_known_poses.py`

**Interfaces:**
- `estimate_adaptive_turntable_angles(...)` adds `axis_xyz` and axis diagnostics to its result/report.
- `build_pose_records(..., axis_xyz=(0.0, 1.0, 0.0))` creates axis-angle quaternions.

- [ ] Write a failing test showing a tilted axis produces the expected quaternion/camera ring.
- [ ] Run focused tests and verify RED.
- [ ] Implement axis estimation with camera-Y fallback when fewer than three reliable axis measurements exist or axis consistency is poor.
- [ ] Pass the recovered axis into both CW/CCW known-pose candidates.
- [ ] Run Turntable focused tests, then the full Python suite.
- [ ] Re-run Sparse for `hlw_04` and compare point count, track length, reprojection error, camera ring, and diagnostics before running Mesh/Splat.

### Task 3B: Turntable matching enhancement, only if Task 2 supports it

**Files:**
- Modify: `pipeline/turntable.py`
- Modify: Turntable command-contract tests.

- [ ] Write failing tests asserting Turntable-only feature extraction uses affine-shape + DSP-SIFT and that small Turntable frame sets use exhaustive matching.
- [ ] Verify RED.
- [ ] Add `--SiftExtraction.estimate_affine_shape 1` and `--SiftExtraction.domain_size_pooling 1` to Turntable mask-guided extraction.
- [ ] For a small Turntable image set, use `exhaustive_matcher` with guided matching; retain bounded sequential matching for large sets.
- [ ] Run focused tests and full suite.
- [ ] Re-run Sparse and compare graph coverage, sparse points, and mean track length before any dense route.

### Task 4: Dense-route regression only after Sparse improves

- [ ] Re-run Mesh → GLB and Splat → PLY from the same improved Shared Sparse.
- [ ] Compare against the saved failed outputs from `hlw_04`.
- [ ] Do not tune OpenMVS or Brush unless Shared Sparse metrics improve but dense outputs remain independently poor.
