# Turntable R0.2b-2.1 Stable Joint Objective Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:test-driven-development and
> superpowers:verification-before-completion.

**Goal:** Stabilize the GT-free free-span alternating solver without changing
the validated R0.2a/R0.2b-1 mathematical primitives.

### Task 1: Unified joint objective

**Files:**
- Modify: `pipeline/workflows/turntable/pose/joint_refine.py`
- Test: `tests/test_turntable_research_r02b21.py`

- [x] Define full-adjacent-pair trimmed-RMS Sampson objective.
- [x] Make positive angle fitting minimize the same per-pair term.
- [x] Add monotonic accepted-objective regression.

### Task 2: Candidate acceptance and best state

**Files:**
- Modify: `pipeline/workflows/turntable/pose/joint_refine.py`
- Test: `tests/test_turntable_research_r02b21.py`

- [x] Score angle and geometry proposals against one `J`.
- [x] Reject non-improving proposals.
- [x] Retain and return the best accepted state.
- [x] Add `stable_state`, `objective_patience`, `max_iterations`.
- [x] Record accepted/rejected blocks and objective history.

### Task 3: Zero-inlier initialization bug

**Files:**
- Modify: `pipeline/workflows/turntable/pose/initialization.py`
- Test: `tests/test_turntable_research_r02b21.py`

- [x] RED: zero-inlier `recoverPose()` hypothesis must be rejected.
- [x] Reject `inliers <= 0` before angle/axis candidate creation.

### Task 4: Benchmark reporting

**Files:**
- Modify: `tools/turntable_r02b2_joint_benchmark.py`

- [x] Default maximum iterations to 20.
- [x] Report unified joint objective.
- [x] Report termination reason.
- [x] Report `best_state_returned`.
- [x] Report accepted joint-objective history.

### Task 5: Preservation contracts

- [x] Carry BUG-0014 lock/snapshot files and tests forward.
- [x] Keep R0.2a/R0.2b-1 math files untouched.
- [x] Preserve invalid RotGS HTML sanitation behavior.
