# Videoto3D V1.4 Capture-Method Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish two peer capture-method workflows while preserving stable Orbit Camera reconstruction and isolating Turntable research.

**Architecture:** A workflow registry maps immutable Run `capture_mode` to Orbit Camera or Turntable. Shared low-level COLMAP/OpenMVS/Brush/Blender infrastructure stays in place. The web Run detail page becomes a thin router to capture-specific views.

**Tech Stack:** Python 3.11, COLMAP, FastAPI, React/TypeScript, pytest.

## Global Constraints
- Canonical CLI entry is `python Videoto3D.py ...`.
- Use only Orbit Camera / `orbit_camera` and Turntable / `turntable`.
- Orbit Camera pose recovery is full-RGB incremental SfM with `mask_path=None`.
- Turntable V1.3 code is frozen under `pipeline/workflows/turntable/legacy_v13/`.
- Existing `workspace/runs/<run_id>` layout is preserved.
- OpenMVS / Brush / Blender / GLB / PLY are not redesigned in Phase 1.

## Tasks
1. Add workflow registry and capture-specific backend sparse runners.
2. Add project-named CLI entry and update bootstrap/GUI jobs.
3. Make Run capture method immutable after source/extract.
4. Split Orbit Camera and Turntable Run views; keep capture selection in New Run.
5. Rewrite README, add ADR/tests, run full verification and real Orbit regression.
