# V1.3.4.1 Turntable Pose A/B Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated diagnostic command that triangulates legacy and constrained Turntable pose trajectories against one existing COLMAP database and reports their sparse-model metrics side by side.

**Architecture:** Keep all production reconstruction files unchanged. A standalone tool imports the existing Turntable angle readers/solver and known-pose triangulation helpers, writes only below `colmap/diagnostics/pose_ab_v1341`, and emits `pose_ab_report.json`.

**Tech Stack:** Python 3.11, NumPy through existing `pipeline.turntable_angle`, COLMAP 4.1.1 CLI, pytest.

## Global Constraints

- Do not modify `colmap/sparse/0`.
- Do not rerun feature extraction or matching.
- Do not alter `database.db`.
- Keep Mesh/GLB and Splat/PLY routes unchanged.
- Use the existing CW/CCW known-pose triangulation and candidate-selection behavior.

---

### Task 1: Diagnostic contract helpers

**Files:**
- Create: `tools/turntable_pose_ab_v1341.py`
- Create: `tests/test_turntable_pose_ab_v1341.py`

- [x] Write failing tests for diagnostics-only paths, estimator summaries, and metric deltas.
- [x] Run the tests and confirm RED because the tool module does not exist.
- [x] Implement the minimal helpers.
- [x] Run the tests and confirm GREEN.

### Task 2: Same-database A/B triangulation

**Files:**
- Modify: `tools/turntable_pose_ab_v1341.py`

- [x] Read legacy and constrained constraints from the existing database.
- [x] Solve a free-span trajectory for each estimator.
- [x] Generate CW/CCW known-pose candidates below the diagnostics root only.
- [x] Run `point_triangulator` and `model_analyzer` using existing pipeline helpers.
- [x] Select the best direction using the existing production rule.
- [x] Write a report with selected metrics and constrained-minus-legacy deltas.

### Task 3: Verification and packaging

**Files:**
- Create: `docs/superpowers/specs/2026-08-18-v1341-turntable-pose-ab-benchmark-design.md`
- Create: `docs/superpowers/plans/2026-08-18-v1341-turntable-pose-ab-benchmark-plan.md`

- [x] Run the V1.3.4 angle/constrained tests plus the new benchmark tests.
- [x] Compile the new tool.
- [ ] Apply the overlay to the real Windows workspace and run `python tools/turntable_pose_ab_v1341.py --run hlw_04`.
- [ ] Review `pose_ab_report.json` before deciding whether to enhance matching or revise constrained angle estimation.
