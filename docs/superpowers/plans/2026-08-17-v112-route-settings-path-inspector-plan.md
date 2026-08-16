# V1.1.2 Route Settings & Path Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the V1.x Studio foundation with safe Mesh controls, read-only paths/runtime inspection, and a complete core environment.

**Architecture:** Core CLI remains authoritative. GUI sends a validated Mesh profile to `route mesh`; OpenMVS records the profile and invalidates only affected downstream stages. Project/runtime paths are exposed through a read-only control-layer API; reusable viewer stays independent.

**Tech Stack:** Python 3.11, unittest, FastAPI, React 18, TypeScript, OpenMVS/COLMAP CLI.

## Global Constraints
- Do not alter SAM2, Splat cleanup, Brush training, or Shared RGB SfM architecture.
- OpenMVS 2.4.0 seam-leveling workaround remains locked OFF.
- Path inspector is read-only.
- All project Python environments remain under `env/` and are ignored by Git.
- GUI delegates reconstruction to core CLI jobs.

---

### Task 1: Core environment completeness
**Files:** `config/envs/core.yml`, `pipeline/env_manager.py`, `tests/test_env_manager.py`
- [ ] Add failing tests requiring Pillow in recipe and core import probe.
- [ ] Run focused tests and verify failure.
- [ ] Add Pillow and PIL health probe.
- [ ] Re-run focused tests.

### Task 2: Mesh profile and recipe-aware OpenMVS
**Files:** `pipeline/openmvs.py`, `tests/test_openmvs.py`
- [ ] Add failing tests for profile-aware args and invalidation boundary.
- [ ] Implement defaults/profile normalization/recipe persistence.
- [ ] Pass profile values into undistort/dense/refine builders.
- [ ] Re-run focused tests.

### Task 3: CLI Mesh settings
**Files:** `pipeline/cli_commands.py`, `app.py`, `tests/test_cli_v11.py`
- [ ] Add failing parser/orchestration tests.
- [ ] Add Mesh option names and numeric validation.
- [ ] Propagate profile to `run_mesh_pipeline` and record it in manifest.
- [ ] Make route skip depend on matching recipe.
- [ ] Re-run focused tests.

### Task 4: GUI API and path inspector data
**Files:** `gui/control/server/app.py`, `gui/control/server/service.py`, `tests/test_gui_api.py`
- [ ] Add failing tests for Mesh JSON payload and runtime/path response.
- [ ] Add `_mesh_args` validation and `POST route/mesh` JSON body.
- [ ] Add read-only runtime/run paths to run detail.
- [ ] Re-run focused tests.

### Task 5: GUI frontend settings and path inspector
**Files:** `gui/control/web/src/types.ts`, `api.ts`, `pages/RunDetailPage.tsx`, `styles.css`, tests.
- [ ] Add failing frontend contract tests.
- [ ] Add Mesh Settings form with safe fields and locked texture workaround note.
- [ ] Add Paths & Runtime grouped read-only panel and Copy Path buttons.
- [ ] Initialize Mesh settings from recorded recipe when available.
- [ ] Re-run contract/syntax tests.

### Task 6: Release docs and verification
**Files:** `README.md`, `gui/README.md`, bug/docs as needed.
- [ ] Update version/commands/path/settings docs and GitHub publishing notes.
- [ ] Run full unittest suite.
- [ ] Run `compileall`.
- [ ] Run TS/TSX syntax parse.
- [ ] Build patch ZIP and fresh-overlay verify.
