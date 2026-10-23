# Turntable R0.4/R0.5 Fast GLB Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development.

**Goal:** Produce a stable GT-free global orbit and feed it through known-pose COLMAP -> existing OpenMVS -> existing Blender GLB export.

**Architecture:** Add one pose module for robust graph least squares, one geometry module for COLMAP known-pose model generation, and two direct CLI tools. Reuse existing OpenMVS and Blender production functions instead of duplicating their pipelines.

**Tech Stack:** Python, NumPy, SQLite, COLMAP 4.1.x CLI, OpenMVS, Blender 5.x.

**Spec:** `docs/superpowers/specs/2026-08-19-turntable-r04-r05-fast-glb-design.md`

## Global Constraints
- No GT angles or GT span in estimation.
- No forced 360-degree normalization.
- R0.2/R0.3 math modules remain frozen.
- BUG-0014 files remain included.
- All new outputs stay under `workspace/research/turntable`.
- Existing OpenMVS and Blender pipelines are reused.

### Task 1: R0.4 robust global orbit
- [ ] RED tests for graph matrix construction, gap5 gating, positive monotonic trajectory, and no 360 normalization.
- [ ] Implement `solve_global_orbit`.
- [ ] GREEN tests.

### Task 2: COLMAP known-pose model
- [ ] RED tests for virtual relative-pose consistency, quaternion conversion, database-ID mapping, and required empty second lines in images.txt.
- [ ] Implement `known_pose_colmap.py`.
- [ ] GREEN tests.

### Task 3: R0.4 CLI
- [ ] RED entrypoint test.
- [ ] Load R0.3c report and R0.3b shared geometry.
- [ ] Solve orbit and write `r04_global_orbit.json`.
- [ ] Load synthetic GT only after prediction for evaluation.
- [ ] GREEN entrypoint test.

### Task 4: R0.5 GLB CLI
- [ ] RED command-builder / `--help` tests.
- [ ] Run feature extraction, sequential matching, manual known-pose model, point triangulation.
- [ ] Call existing `run_mesh_pipeline`.
- [ ] Call existing `export_obj_to_glb`.
- [ ] Write `r05_fast_glb_report.json`.
- [ ] GREEN tests.

### Task 5: Packaging
- [ ] Updater requires `research/turntable-global-orbit`.
- [ ] Preserve R0.3c and BUG-0014.
- [ ] Syntax compile and targeted regressions.
- [ ] ZIP CRC and SHA256.
