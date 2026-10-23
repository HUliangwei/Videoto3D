# Turntable R0.1 Synthetic Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ground-truth synthetic Turntable benchmark and generic single-axis geometry primitives without touching stable reconstruction routes.

**Architecture:** Pure Python modules define geometry, deterministic angle profiles and metrics. A Blender-only tool renders a fixed-camera rotating-object dataset under the project workspace.

**Tech Stack:** Python 3.11, NumPy, pytest, Blender Python API.

**Spec:** `docs/superpowers/specs/2026-08-18-turntable-r01-synthetic-benchmark-design.md`

## Global Constraints
- Orbit Camera unchanged.
- `legacy_v13` frozen.
- No GLB/PLY downstream changes.
- Research data under `workspace/research/turntable/`.

---

### Task 1: Single-axis structured geometry
- [x] RED tests for SO(3), axis invariance, orbit-coupled translation and essential rank.
- [x] Minimal implementation in `pose/single_axis.py`.
- [x] GREEN isolated tests.

### Task 2: GT profiles and metrics
- [x] Test exact span, monotonicity, non-uniformity and gauge alignment.
- [x] Implement deterministic profiles.
- [x] Implement axis/angle/increment/span metrics.

### Task 3: Blender synthetic renderer
- [x] Implement fixed-camera GLB/GLTF renderer.
- [x] Emit RGBA frames, alpha masks and GT metadata.
- [ ] Validate against the user's installed Blender and an actual Orbit Camera GLB.

### Task 4: Benchmark report tool
- [x] Implement compact prediction scoring.
- [x] CPython smoke test with gauge-equivalent perfect prediction.
- [ ] Use on first R0.2 solver output.

### Task 5: Documentation
- [x] Add research roadmap.
- [x] Separate paper-derived ideas from Videoto3D extensions.
- [x] Record staged promotion criteria.
