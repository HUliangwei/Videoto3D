# Turntable R0.2b-1 Shared Observable Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover shared observable Turntable geometry with GT relative
angles but without GT axis/orbit.

**Architecture:** Multiple masked image pairs share one orthonormal
observable frame `Q=[u,a×u,a]`. A trimmed Sampson objective is optimized
by deterministic SO(3) coarse search plus multi-seed frame refinement.

**Tech Stack:** Python 3.11, NumPy, OpenCV 4.13 headless, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-turntable-r02b1-shared-geometry-design.md`

## Global Constraints

- Orbit Camera remains unchanged.
- `pipeline/workflows/turntable/legacy_v13/` remains unchanged.
- R0.2b-1 does not enter production Sparse / GLB / PLY routes.
- GT signed pair angles are allowed; GT axis/orbit are evaluation-only.
- Preserve BUG-0014 Splat lock and Viewer snapshot.
- `env/core` owns `opencv-python-headless==4.13.0.92`.

---

### Task 1: Observable geometry primitives

**Files:**
- Create: `pipeline/workflows/turntable/pose/shared_geometry.py`
- Test: `tests/test_turntable_research_r02b1.py`

**Interfaces:**
- Produces: `observable_transverse_orbit`, `observable_geometry_frame`,
  `line_angle_error_deg`.

- [x] Write RED tests for axial/scale observability and sign gauge.
- [x] Run tests and confirm failure because the module is absent.
- [x] Implement normalized transverse-orbit representation.
- [x] Run tests and confirm GREEN.

### Task 2: Shared geometry estimator

**Files:**
- Modify: `pipeline/workflows/turntable/pose/shared_geometry.py`
- Test: `tests/test_turntable_research_r02b1.py`

**Interfaces:**
- Consumes: normalized pair observations + signed delta angles.
- Produces: `estimate_shared_geometry(...) -> dict`.

- [x] Write multi-pair exact recovery test.
- [x] Implement prepared-pair observations and trimmed Sampson objective.
- [x] Implement deterministic SO(3) coarse search.
- [x] Implement multi-seed local frame refinement.
- [x] Run the isolated estimator tests and confirm GREEN.

### Task 3: Image benchmark

**Files:**
- Create: `tools/turntable_r02b1_shared_geometry_benchmark.py`

**Interfaces:**
- Consumes: R0.1 synthetic frames/masks/GT K and GT signed delta.
- Produces:
  `workspace/research/turntable/r02b1/<dataset>/shared_geometry_report.json`.

- [x] Select evenly spaced adjacent pairs.
- [x] Build masked SIFT observations.
- [x] Keep GT axis/orbit out of optimizer inputs.
- [x] Load GT axis/orbit only after fitting for metrics.
- [ ] Run on `chair_nonuniform_280`.

### Task 4: Research tool entrypoints

**Files:**
- Modify: `tools/turntable_r02_pair_benchmark.py`
- Modify: `tools/turntable_r02_sequence_benchmark.py`
- Test: `tests/test_turntable_research_tool_entrypoints.py`

- [x] Add a direct-script `--help` regression test.
- [x] Inject repository root before `pipeline` imports.
- [x] Preserve `python -m tools...` operation.

### Task 5: Core OpenCV integration

**Files:**
- Modify: `config/envs/core.yml`
- Modify: `pipeline/env_manager.py`
- Modify: `app.py`
- Test: `tests/test_core_opencv_runtime.py`

- [x] Pin `opencv-python-headless==4.13.0.92` in core recipe.
- [x] Require `cv2` and `SIFT_create` in core validation.
- [x] Add explicit Core CV runtime health to env status and doctor.
- [ ] Verify the user's Windows bootstrap reconciles the stale core recipe.

### Task 6: Preserve BUG-0014

**Files:**
- Preserve: `pipeline/run_lock.py`
- Preserve: `pipeline/viewer_snapshot.py`
- Test: `tests/test_v14_splat_concurrency_guard.py`

- [x] Carry the cross-process lock implementation forward.
- [x] Carry immutable Viewer snapshot implementation forward.
- [x] Carry regression tests forward.
- [ ] Perform real Windows GUI + CLI contention verification later.
