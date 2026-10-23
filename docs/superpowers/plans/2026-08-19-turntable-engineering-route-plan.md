# Turntable Engineering Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development.

**Goal:** Integrate the validated Turntable sparse path into canonical `run ...` / `route mesh` commands and keep every Run artifact inside its Run workspace.

**Architecture:** A Turntable engineering stage module owns stage execution and Run-local artifacts. A thin CLI compatibility wrapper adds four debug commands without rewriting the existing parser. `app.py` dispatches by `run.json` capture mode and preserves shared Mesh/GLB stages.

**Tech Stack:** Python, NumPy, OpenCV feature matching, COLMAP CLI, existing OpenMVS/Blender modules.

**Spec:** `docs/superpowers/specs/2026-08-19-turntable-engineering-route-design.md`

## Global constraints
- Canonical entry remains `Videoto3D.py`.
- Final user interface remains `route mesh`.
- Run data stays strictly below `workspace/runs/<run_id>`.
- Orbit Camera is unchanged.
- BUG-0014 remains shipped.

## Tasks
1. Add CLI wrapper and RED/GREEN parser tests.
2. Add Run-local Turntable stage state/path helpers and RED/GREEN confinement tests.
3. Add anchor/pairs/orbit/triangulate stage implementation.
4. Patch app.py dispatch and invalidation rules.
5. Verify source contract, prior R0.3/R0.4 tests, BUG-0014, updater fixture and ZIP CRC.
