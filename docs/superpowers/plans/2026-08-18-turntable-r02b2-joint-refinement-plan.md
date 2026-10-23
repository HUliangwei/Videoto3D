# Turntable R0.2b-2 Joint Alternating Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans. Implement task-by-task with TDD.

**Goal:** Achieve a GT-pose-free, free-span, non-uniform synthetic
Turntable pose estimate by composing the validated R0.2a and R0.2b-1
primitives.

**Architecture:** Generic Essential pose hypotheses provide a GT-free
initial shared frame and positive adjacent angle magnitudes. An
angle-first alternating loop repeatedly performs structured positive
angle fitting and global shared-geometry fitting.

**Tech Stack:** Python 3.11, NumPy, OpenCV 4.13 headless, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-turntable-r02b2-joint-refinement-design.md`

## Constraints

- Do not modify `structured_fit.py`.
- Do not modify `shared_geometry.py`.
- Do not modify Orbit Camera.
- Do not modify frozen `legacy_v13`.
- Do not force total span to 360 degrees.
- GT axis/orbit/angles/span are evaluation-only.
- Preserve BUG-0014 Splat lock and immutable Viewer snapshot.
- Do not depend on the invalid RotGS HTML file as a paper source.

### Task 1: GT-free generic Essential initialization

**Files:**
- Create: `pipeline/workflows/turntable/pose/initialization.py`
- Test: `tests/test_turntable_research_r02b2.py`

- [x] RED tests for rotation-angle extraction and line aggregation.
- [x] Add lazy OpenCV pair pose recovery.
- [x] Reject implausible/180-degree pair rotations.
- [x] Aggregate axis/transverse line candidates with robust weights.
- [x] Use median accepted delta for failed local pairs only.

### Task 2: Free-span alternating joint solver

**Files:**
- Create: `pipeline/workflows/turntable/pose/joint_refine.py`
- Test: `tests/test_turntable_research_r02b2.py`

- [x] Add prepared normalized pair observations.
- [x] Add positive-only R0.2a-style angle fit.
- [x] Run angle-first -> geometry -> angle schedule.
- [x] Reuse R0.2b-1 global geometry estimator unchanged.
- [x] Add convergence history.
- [x] Prove a short free-span synthetic sequence does not normalize to 360.

### Task 3: End-to-end synthetic benchmark

**Files:**
- Create: `tools/turntable_r02b2_joint_benchmark.py`
- Test: `tests/test_turntable_research_r02b2_entrypoint.py`

- [x] Build all adjacent masked SIFT correspondences once.
- [x] Run GT-free generic Essential initialization.
- [x] Run joint refinement.
- [x] Read GT pose only after optimization.
- [x] Emit initial-vs-final metrics and convergence history.
- [ ] Run `chair_nonuniform_280`.

### Task 4: Research paper asset hygiene

**Files:**
- Create: `docs/research/turntable/papers/README.md`
- Test: `tests/test_turntable_research_paper_assets.py`
- Update overlay script.

- [x] Keep the valid Kosaka PDF.
- [x] Detect a `.pdf` whose signature is HTML rather than `%PDF-`.
- [x] Rename invalid RotGS download to `.invalid.html` without deleting it.
- [x] Document that RotGS is not required until the later Gaussian stage.
- [ ] Replace it with a genuine PDF only when an authoritative PDF is available.

### Task 5: Preserve V1.4 BUG-0014

**Files:**
- Preserve: `pipeline/run_lock.py`
- Preserve: `pipeline/viewer_snapshot.py`
- Preserve: `tests/test_v14_splat_concurrency_guard.py`

- [x] Carry the guard files into the overlay.
- [x] Updater verifies the Splat route still uses the cross-process lock.
- [x] Updater verifies Brush Viewer still uses a snapshot.
