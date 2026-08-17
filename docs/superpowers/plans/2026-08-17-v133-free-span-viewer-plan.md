# V1.3.3 Free-Span Turntable + Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the hard 360° Turntable pose assumption while adding fit-first zoom/pan artifact previews without changing the GLB/PLY reconstruction backends.

**Architecture:** Keep `run_turntable_reconstruction()` and its known-pose CW/CCW `point_triangulator` boundary intact. Replace only the angle estimator with a bounded multi-pair one-dimensional constraint graph; update image preview interaction and make the existing 3D viewer preserve Auto Fit across container resize until manual interaction.

**Tech Stack:** Python 3.9, NumPy, COLMAP SQLite geometry, React 18, TypeScript, Three.js.

## Global Constraints

- Do not change Mesh Route or Splat Route APIs, commands, or output locations.
- Do not require an exact 360° turn.
- Keep the camera-fixed, rigid-subject, single-axis, primarily one-direction Turntable capture contract.
- Add no new Python or npm runtime dependency.

---

### Task 1: Free-span Turntable angle graph

**Files:**
- Modify: `pipeline/turntable_angle.py`
- Test: `tests/test_turntable_adaptive_angle.py`

**Interfaces:**
- Consumes: existing `estimate_adaptive_turntable_angles(database_path, images, camera, min_inliers=12)` call from `pipeline/turntable.py`.
- Produces: the same top-level result shape, with `angles_rad` feeding existing known poses and a report strategy of `adaptive_free_span_graph`.

- [x] Add failing tests for non-360 total span and missing-adjacent geometry bridged by multi-frame pairs.
- [x] Add pair-id decoding and bounded multi-pair geometry extraction.
- [x] Solve positive per-frame increments with robust weighted least squares and weak priors.
- [x] Preserve legacy V1.3.2 helper functions for compatibility but stop calling full-turn normalization in the reconstruction path.
- [x] Run focused Python tests.

### Task 2: Fit-first artifact viewer

**Files:**
- Modify: `gui/control/web/src/components/ArtifactInspector.tsx`
- Modify: `gui/control/web/src/components/artifact-inspector.css`
- Modify: `gui/viewer/src/AssetViewer.tsx`

**Interfaces:**
- Consumes: existing artifact URLs and `AssetViewer` props.
- Produces: no API changes; only interaction behavior changes.

- [x] Wrap image/mask content in an interactive fit/zoom/pan viewport.
- [x] Reset image fit when frame or mask mode changes.
- [x] Make 3D fit aspect-aware and resize-aware until manual interaction.
- [x] Keep existing Three.js rotate/pan/wheel controls.
- [x] Run TypeScript syntax transpilation checks.

### Task 3: Capture-mode copy and regression contract

**Files:**
- Modify: `pipeline/capture_mode.py`
- Create: `tests/test_v133_free_span_viewer_contract.py`
- Create: `docs/architecture/ADR-0013-turntable-free-span-angle-graph.md`
- Create: `docs/guides/Turntable_Free_Span_v133.md`
- Create: `docs/guides/Viewer_Auto_Fit_v133.md`

- [x] Replace obsolete `Adaptive 360°` capture label with `Free-span angle graph`.
- [x] Assert that existing `pipeline/turntable.py` still uses `point_triangulator` and the same adaptive estimator entry point.
- [x] Document that 360° is a surface-coverage recommendation rather than a pose requirement.
