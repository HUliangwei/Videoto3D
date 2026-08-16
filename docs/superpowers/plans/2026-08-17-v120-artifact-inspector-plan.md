# Videoto3D V1.2.0 Artifact Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Pipeline Artifact Inspector that previews every important Shared/Mesh/Splat intermediate result in the Local Web Studio.

**Architecture:** `gui/control` discovers and serves Videoto3D-specific run artifacts. The reusable `gui/viewer` is extended only with generic PLY point-cloud/mesh support. The Run page loads artifact metadata separately and opens one preview at a time.

**Tech Stack:** Python 3.11+, FastAPI, React 18, TypeScript, Three.js 0.180, Spark 2.1.

## Global Constraints

- Preserve `gui/control` vs `gui/viewer` boundary.
- Do not add another reconstruction algorithm.
- Do not mutate intermediate artifacts from the inspector.
- No arbitrary filesystem path is accepted from the browser.
- Keep `runtime/`, `workspace/`, and `env/` out of Git.

---

### Task 1: Artifact catalog and safe resolvers

**Files:**
- Create: `gui/control/server/artifacts.py`
- Test: `tests/test_gui_artifacts.py`

- [ ] Write tests for Shared/Mesh/Splat artifact discovery, partial masks, PLY counts, COLMAP PLY conversion, and safe indexed resolution.
- [ ] Verify tests fail because `artifacts.py` does not exist.
- [ ] Implement fixed-layout artifact discovery and binary PLY conversion.
- [ ] Run artifact tests.

### Task 2: Read-only artifact API

**Files:**
- Modify: `gui/control/server/app.py`
- Test: `tests/test_gui_artifacts.py`

- [ ] Add failing API contract assertions for catalog, images, generated sparse PLY, and unknown keys.
- [ ] Add five read-only artifact routes.
- [ ] Run backend tests.

### Task 3: Generic PLY viewer

**Files:**
- Modify: `gui/viewer/src/AssetViewer.tsx`
- Test: `tests/test_gui_viewer_artifact_types.py`

- [ ] Add contract test requiring `pointcloud`, `mesh-ply`, and `PLYLoader`.
- [ ] Extend the generic viewer with PLY points and PLY mesh loading.
- [ ] Keep existing GLB/Splat controls and free camera roll unchanged.

### Task 4: Artifact Inspector UI

**Files:**
- Create: `gui/control/web/src/components/ArtifactInspector.tsx`
- Create: `gui/control/web/src/components/artifact-inspector.css`
- Modify: `gui/control/web/src/types.ts`
- Modify: `gui/control/web/src/api.ts`
- Modify: `gui/control/web/src/pages/RunDetailPage.tsx`
- Modify: `gui/control/web/src/App.tsx`
- Test: `tests/test_gui_frontend_artifacts_contract.py`

- [ ] Add failing frontend contract tests.
- [ ] Add catalog types/API client.
- [ ] Implement grouped cards, status labels, sequence controls, mask Original/Mask/Overlay, and modal 3D viewer.
- [ ] Insert Pipeline Artifacts between Route Control and Result Viewer.
- [ ] Update Studio label to V1.2.0.

### Task 5: Documentation and release verification

**Files:**
- Create: `docs/architecture/ADR-0009-artifact-inspector.md`
- Create: `docs/guides/Videoto3D_Workflow_Video_Recording.md`

- [ ] Document component boundary and media recording workflow.
- [ ] Run Python unit tests available in the execution environment.
- [ ] Run `python -m compileall` on modified Python files.
- [ ] Run TypeScript syntax/transpile checks available in the execution environment.
- [ ] Build a clean overlay ZIP containing only new/modified tracked source files.
