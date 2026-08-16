# Videoto3D V0.10 Dual Route Run Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a flat dual-route Run layout, schema-v3 progress, one-command route orchestration, and object-only Brush initialization.

**Architecture:** Shared FFmpeg/SAM2/COLMAP assets stay directly under each Run. Mesh and Splat private intermediates move under `mesh/` and `splat/`, while manifest state is nested into `shared` and `routes`. Splat initialization filters only COLMAP 3D points using existing SAM2 masks and preserves all camera poses.

**Tech Stack:** Python 3.9+, COLMAP binary model format, SAM2 mask PNG, OpenMVS, Brush, Blender.

## Global Constraints

- Preserve all user data during V0.9 → V0.10 migration.
- Do not rerun masked SfM for Splat isolation.
- Keep final GLB and Splat PLY together under `output/`.
- Keep OpenMVS 2.4.0 seam-leveling workaround.
- Keep GUI viewers detached.
- Update README for every canonical CLI change.

---

### Task 1: Manifest v3 and layout migration
**Files:** `pipeline/run_workspace.py`, `tests/test_run_workspace.py`
- [ ] Add failing tests for new directories, schema v3, nested status and V0.9 migration.
- [ ] Implement non-destructive directory migration and manifest conversion.
- [ ] Run focused tests.

### Task 2: Object-only COLMAP filter
**Files:** `pipeline/colmap_object.py`, `tests/test_colmap_object.py`
- [ ] Add synthetic COLMAP binary + PNG mask tests.
- [ ] Implement binary readers/writers and mask voting filter.
- [ ] Write object sparse report.
- [ ] Run focused tests.

### Task 3: Brush and Mesh route paths
**Files:** `pipeline/brush.py`, `app.py`, `tests/test_brush.py`, `tests/test_cli.py`
- [ ] Add failing path/isolation tests.
- [ ] Move Mesh intermediates under `mesh/` and Splat intermediates under `splat/`.
- [ ] Integrate object-only filtering before Brush training.
- [ ] Preserve route outputs independently.

### Task 4: Route CLI and progress
**Files:** `pipeline/cli_commands.py`, `app.py`, `tests/test_cli_v10.py`
- [ ] Add `route mesh`, `route splat`, `view splat-init` parsing tests.
- [ ] Add route orchestration with cache skips and optional input.
- [ ] Change `runs list/show` to Shared / Mesh Route / Splat Route output.

### Task 5: Documentation and verification
**Files:** `README.md`, `docs/architecture/ADR-0003-dual-route-run-layout.md`, tests
- [ ] Update README commands/layout/migration/usage.
- [ ] Add ADR and object-sparse troubleshooting notes.
- [ ] Run full unit suite, compileall and CLI smoke tests.
- [ ] Build fresh-overlay ZIP and verify again.
