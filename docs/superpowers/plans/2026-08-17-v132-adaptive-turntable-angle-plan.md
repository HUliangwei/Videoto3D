# Adaptive Turntable Angle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimate non-uniform per-frame Turntable angles from COLMAP verified pair geometry and reuse the existing known-pose Mesh/Splat pipeline.

**Architecture:** A focused `pipeline/turntable_angle.py` reads `two_view_geometries`, derives adjacent relative-rotation magnitudes, robustly smooths and normalizes them, and returns a monotonic angle vector. `pipeline/turntable.py` consumes that vector instead of uniform angles.

**Tech Stack:** Python 3.11, NumPy, SQLite, COLMAP database, existing Pillow/core pipeline.

## Global Constraints

- Manual Orbit/Turntable selector remains.
- Orbit path is unchanged.
- Turntable no longer requires uniform speed.
- Turntable still requires one approximately full monotonic 360° rigid rotation and fixed camera.
- Mesh/Splat downstream code remains unchanged.
- No new Python dependency: NumPy is already in `env/core`.

---

### Task 1: Pairwise epipolar angle estimator
- [x] Write RED import test.
- [x] Implement pair-id handling, F/E decoding, essential decomposition and adjacent angle extraction.
- [x] Verify synthetic essential matrices recover 1.5°–18° rotations.

### Task 2: Robust trajectory
- [x] Fill missing pairs, reject isolated outliers, lightly smooth, retain speed variation.
- [x] Normalize to the full-turn span and cumulatively integrate.
- [x] Add uniform fallback when verified-pair coverage is insufficient.
- [x] Verify monotonic angles and non-uniform ratio preservation.

### Task 3: Known-pose integration
- [x] Add variable-angle pose builder.
- [x] Write `turntable_angle_report.json`.
- [x] Preserve CW/CCW triangulation and candidate selection.
- [x] Keep `colmap/sparse/0` output contract.

### Task 4: App/docs
- [x] Record adaptive/fallback pose strategy and angle-report path in Shared Sparse manifest.
- [x] Update README and engineering docs.
- [x] Add regression tests.

### Task 5: Verification
- [x] Fresh Python syntax validation.
- [x] Synthetic unit/contract tests.
- [x] ZIP exclusion checks.
- [ ] User Windows full pytest.
- [ ] User GUI production build.
- [ ] New real Turntable run through Mesh and Splat.
