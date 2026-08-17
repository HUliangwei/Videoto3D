# Turntable Uniform-360 Known-Pose Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace V1.3 Turntable's free mapper pose estimation with uniform full-turn known poses while leaving Orbit and both reconstruction routes intact.

**Architecture:** `pipeline/turntable.py` owns Turntable feature extraction, matching, known-pose model generation, two-direction triangulation, and sparse-model selection. `app.py::run_sparse` is the only branch point.

**Tech Stack:** Python 3.11, Pillow, SQLite, COLMAP 4.x CLI, existing Videoto3D manifests.

## Global Constraints

- Manual `orbit_camera|turntable` selection remains.
- Orbit Camera is unchanged.
- Turntable input is one roughly uniform complete 360° rigid rotation with fixed, approximately level camera.
- Mesh/Splat code paths and output formats are unchanged.
- Patch excludes `.git`, `env`, `runtime`, `workspace`, and `recordings`.

---

### Task 1: Known-pose geometry and COLMAP model IO
- [x] Write failing import/pose tests.
- [x] Verify RED.
- [x] Implement DB camera/image parsing, mask-center translation estimate, pose-ring generation, quaternion/camera-center math, and known-pose TXT model writer.
- [x] Verify GREEN.

### Task 2: Turntable sparse runner
- [x] Implement mask-guided features + sequential guided matching.
- [x] Generate CW/CCW known-pose candidates.
- [x] Triangulate each with COLMAP `point_triangulator`.
- [x] Select by sparse point count, then reprojection error.
- [x] Copy standard binary model to `colmap/sparse/0`.

### Task 3: Shared Sparse branch
- [x] Patch only `app.py::run_sparse`.
- [x] Orbit invokes existing `run_sparse_reconstruction`.
- [x] Turntable invokes `run_turntable_reconstruction`.
- [x] Record pose strategy/direction/axis metadata.

### Task 4: User-facing docs and regression record
- [x] Add V1.3.1 capture requirements to README without removing canonical CLI reference.
- [x] Add ADR, bug record, focused guide, design, and plan.

### Task 5: Package verification
- [x] Python AST verification.
- [x] Isolated unit tests.
- [x] Synthetic patch `--check` + apply.
- [x] ZIP exclusion checks.
- [ ] User-machine full pytest and GUI production build.
