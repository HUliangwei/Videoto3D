# V1.3.0 Turntable Capture Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent Orbit/Turntable capture modes, mask-guided COLMAP SfM for Turntable, and camera-trajectory QA without changing the two reconstruction routes.

**Architecture:** Capture mode is Run metadata. Core pipeline selects the COLMAP feature mask; GUI delegates the selected mode to the core CLI. Artifact Inspector visualizes COLMAP camera centers using the generic point-cloud viewer.

**Tech Stack:** Python, COLMAP, FastAPI, React/TypeScript, Three.js generic point-cloud viewer, pytest.

## Global Constraints

- Windows-local-first; no WSL.
- `workspace/`, `runtime/`, `env/`, and `recordings/` remain out of Git.
- `gui/viewer` remains independent from Videoto3D Run concepts.
- Orbit Camera must preserve V1.2 full-RGB Shared SfM.
- Turntable is for rigid subjects; dynamic / articulated human reconstruction is out of scope.

---

### Task 1: Capture-mode domain model

**Files:** `pipeline/capture_mode.py`, `pipeline/run_workspace.py`, `tests/test_capture_mode.py`

- [ ] Add failing tests for normalization, legacy default, persistence and invalid modes.
- [ ] Verify RED.
- [ ] Implement capture-mode helper and manifest persistence.
- [ ] Verify GREEN.

### Task 2: Turntable Shared SfM

**Files:** `app.py`, `pipeline/cli_commands.py`, `tests/test_capture_mode.py`

- [ ] Add failing tests for CLI `--capture-mode` entry points and mask-guided strategy.
- [ ] Verify RED.
- [ ] Route Turntable sparse to existing `run_sparse_reconstruction(..., mask_path=run/masks)`.
- [ ] Invalidate sparse after mask changes only for Turntable.
- [ ] Verify GREEN.

### Task 3: Web control selector

**Files:** `gui/control/server/app.py`, `gui/control/server/service.py`, `gui/control/web/src/api.ts`, `types.ts`, `components/NewRunPanel.tsx`, `pages/RunDetailPage.tsx`, `styles.css`, `tests/test_v130_frontend_contract.py`

- [ ] Add failing frontend/backend contract tests.
- [ ] Verify RED.
- [ ] Add Capture Mode selector and API forwarding.
- [ ] Expose persisted mode in Run detail.
- [ ] Verify GREEN and production frontend build.

### Task 4: Camera trajectory + Quality

**Files:** `gui/control/server/artifacts.py`, `pipeline/quality.py`, `gui/control/web/src/components/QualityPanel.tsx`, `tests/test_turntable_artifacts.py`

- [ ] Write synthetic COLMAP `images.bin` test and verify RED.
- [ ] Parse camera centers `C=-R^Tt` and serialize browser PLY.
- [ ] Add Shared Camera Trajectory artifact.
- [ ] Add capture/sparse strategy to Quality.
- [ ] Verify GREEN.

### Task 5: Documentation and release verification

**Files:** README, ADR-0010, Turntable guide, design/plan docs.

- [ ] Document Orbit vs Turntable and rigid-human boundary.
- [ ] Run `python -m pytest -q`.
- [ ] Run `npm run build` under `gui/`.
- [ ] Run `git diff --check`.
- [ ] Commit only after all checks pass.
