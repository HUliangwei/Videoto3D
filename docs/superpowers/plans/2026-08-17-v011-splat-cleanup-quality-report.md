# V0.11 Splat Cleanup + Quality Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight post-Brush multi-view SAM2 cleanup stage for final Gaussian Splat PLYs and a unified per-run quality report without adding new ML models or changing shared reconstruction stages.

**Architecture:** Keep V0.10 shared frames/masks/COLMAP and both output routes. Brush still trains from the existing object-sparse dataset, but its final checkpoint is preserved as a raw PLY under `splat/raw/`; cleanup projects each final Gaussian center through the original COLMAP cameras, votes against existing SAM2 masks, and writes only supported splats to `output/<run_id>_splat.ply`. Quality reporting reads manifest/files and writes `quality/report.json` plus `quality/report.md` for humans and future GUI use.

**Tech Stack:** Python stdlib, NumPy, existing COLMAP binary helpers, Brush/OpenMVS/Blender adapters.

## Global Constraints

- Do not add a new segmentation model, custom Brush build, RGBA dataset conversion, DBSCAN, or second SfM pass.
- Shared stages remain `extract -> mask -> sparse` and are reused by Mesh and Splat routes.
- Default Splat cleanup policy is `foreground support ratio >= 0.70` with at least `3` valid mask-view projections.
- Existing V0.10 Splat output must migrate non-destructively into a raw cleanup candidate so `teddy_001` can upgrade without retraining Brush.
- `route splat` may rerun cleanup without rerunning Brush when the Brush training recipe still matches.
- Root `README.md` and architecture docs must be updated in the same ZIP.

---

### Task 1: Gaussian PLY + COLMAP multi-view cleanup

**Files:**
- Create: `pipeline/splat_cleanup.py`
- Test: `tests/test_splat_cleanup.py`

**Interfaces:**
- Produces: `cleanup_splat(raw_ply, output_ply, sparse_model, masks_dir, report_path, foreground_ratio=0.70, min_views=3) -> dict`
- Produces: `read_ply_vertex_count(path) -> int`

- [ ] Write failing tests for binary-little-endian Gaussian PLY filtering, COLMAP camera projection, mask consensus, and report metrics.
- [ ] Run `python -m unittest tests.test_splat_cleanup -v` and confirm RED.
- [ ] Implement scalar-property PLY parsing/writing, camera binary parsing, common COLMAP camera projection, vectorized multi-view votes, and report JSON.
- [ ] Re-run focused tests and confirm GREEN.

### Task 2: Raw Brush artifact + cleanup orchestration

**Files:**
- Modify: `pipeline/brush.py`
- Modify: `pipeline/run_workspace.py`
- Modify: `app.py`
- Test: `tests/test_brush.py`
- Test: `tests/test_run_workspace_v11.py`
- Test: `tests/test_cli_v11.py`

**Interfaces:**
- Brush training outputs `splat/raw/<run_id>_raw.ply` instead of treating raw training output as final output.
- Splat route stages are user-facing `training -> cleanup -> ply`; object-sparse filtering remains an internal training optimization/report.

- [ ] Write failing tests for raw PLY preservation, schema-v4 V0.10 migration, cleanup-only resume, and cleanup CLI overrides.
- [ ] Confirm RED.
- [ ] Implement schema-v4 migration and app orchestration.
- [ ] Confirm GREEN.

### Task 3: Unified quality report

**Files:**
- Create: `pipeline/quality.py`
- Modify: `app.py`
- Modify: `pipeline/cli_commands.py`
- Test: `tests/test_quality.py`
- Test: `tests/test_cli_v11.py`

**Interfaces:**
- Produces: `generate_quality_report(run_root) -> dict`
- CLI: `python app.py quality --run <run_id>`
- Files: `quality/report.json`, `quality/report.md`

- [ ] Write failing tests for shared, Mesh, raw/clean Splat metrics and Markdown/JSON output.
- [ ] Confirm RED.
- [ ] Implement report generation and CLI rendering.
- [ ] Confirm GREEN.

### Task 4: Progress UX and documentation

**Files:**
- Modify: `README.md`
- Create: `README_V11_PATCH.txt`
- Create: `docs/architecture/ADR-0004-post-brush-splat-cleanup.md`
- Modify: `tests/test_docs.py`

- [ ] Add failing docs assertions for cleanup, quality, raw/final PLY distinction, and route resume behavior.
- [ ] Confirm RED.
- [ ] Update docs and command help to V0.11.
- [ ] Confirm GREEN.

### Task 5: Full verification and patch packaging

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python -m compileall app.py pipeline scripts tests`.
- [ ] Build a minimal overlay ZIP containing only changed/new V0.11 files.
- [ ] Apply V0.10 ZIP then V0.11 ZIP to a fresh directory and rerun full tests, compileall, `python app.py --help`, and migration smoke tests.
