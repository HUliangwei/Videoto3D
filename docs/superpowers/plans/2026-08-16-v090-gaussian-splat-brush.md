# Videoto3D V0.9 Gaussian Splat / Brush Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, run-local Gaussian Splat output branch using Brush, while keeping the existing OpenMVS→OBJ→GLB branch unchanged.

**Architecture:** Each Run gains a `brush/` subtree containing a deterministic COLMAP+SAM2 staging dataset and Brush exports. `python app.py run splat --run <id>` trains headlessly from that staging dataset and records a canonical final PLY in the Run manifest. `python app.py view splat` launches Brush detached, either from a Run or an arbitrary PLY path. Existing COLMAP/Blender viewers are also launched detached on Windows so closing them does not require Ctrl+C.

**Tech Stack:** Python 3.9 main CLI, Brush native Windows executable, COLMAP sparse model, SAM2 PNG masks, JSON run manifest, unittest.

## Global Constraints

- Keep all Run data under `workspace/runs/<run_id>/`.
- Do not modify source RGB frames or SAM2 masks in-place.
- Reuse the existing COLMAP sparse model; do not rerun SfM for splat training.
- Brush public CLI must be hidden behind `run splat` / `view splat`.
- Default V0.9 Brush profile: 30000 steps, 2000000 max splats, 1280 max resolution, export checkpoint every 5000 steps.
- Preserve V0.7.3 OpenMVS TextureMesh workaround.
- README and run manifest schema must be updated with any new canonical command/stage.

---

### Task 1: Brush adapter and staging

**Files:**
- Create: `pipeline/brush.py`
- Test: `tests/test_brush.py`

**Interfaces:**
- Produces `prepare_brush_dataset(run_root) -> dict`
- Produces `build_brush_train_command(...) -> list[str]`
- Produces `run_brush_training(...) -> dict`
- Produces `launch_brush_viewer(...) -> int`

- [ ] Write tests requiring a staging dataset with `images/`, `masks/`, `sparse/0/`, hardlink/copy-safe file transfer, and canonical Brush arguments.
- [ ] Run tests and confirm RED.
- [ ] Implement the minimal adapter.
- [ ] Run tests and confirm GREEN.

### Task 2: CLI commands and run manifest stage

**Files:**
- Modify: `pipeline/cli_commands.py`
- Modify: `pipeline/run_workspace.py`
- Modify: `app.py`
- Test: `tests/test_cli_v09.py`
- Test: `tests/test_run_workspace.py`

**Interfaces:**
- Adds `run.splat`, `view.splat`.
- Adds options `--steps`, `--max-splats`, `--max-resolution`.
- Adds Run stage `splat` independent from `mesh` and `glb`.

- [ ] Write failing parse/manifest/status tests.
- [ ] Run and confirm RED.
- [ ] Add command registry entries, option validation, app handlers, and manifest fields.
- [ ] Run and confirm GREEN.

### Task 3: Detached viewers

**Files:**
- Modify: `pipeline/blender.py`
- Modify: `pipeline/colmap.py`
- Create: `pipeline/processes.py`
- Test: `tests/test_processes.py`
- Modify: `tests/test_blender.py`
- Modify: `tests/test_colmap.py`

**Interfaces:**
- Produces `launch_detached(command, cwd=None) -> subprocess.Popen`.

- [ ] Write tests for Windows detached flags and stdio redirection.
- [ ] Confirm RED.
- [ ] Implement helper and route viewer launches through it.
- [ ] Confirm GREEN.

### Task 4: Documentation and bug registry

**Files:**
- Modify: `README.md`
- Create: `docs/architecture/ADR-0002-gaussian-splat-branch.md`
- Create: `docs/bugs/BUG-0002-viewer-process-does-not-release-terminal.md`
- Modify: `docs/bugs/README.md`
- Test: `tests/test_docs.py`

- [ ] Add failing docs assertions for `run splat`, `view splat`, SPLAT run table column, and BUG-0002.
- [ ] Confirm RED.
- [ ] Update documentation.
- [ ] Confirm GREEN.

### Task 5: Full verification and packaging

- [ ] Run the complete unittest suite.
- [ ] Run `compileall`.
- [ ] Reconstruct a fresh V0.8 baseline, overlay V0.9 patch, rerun full tests.
- [ ] Package only overwrite files into `Videoto3D_v090_brush_gaussian_splat_patch.zip`.
