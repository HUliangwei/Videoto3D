# Videoto3D V0.7 CLI + Mask-aware OpenMVS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze a normalized Videoto3D CLI, add Chinese command annotations and root README.md, and make the production mesh route use unmasked COLMAP camera poses plus SAM2 masks in OpenMVS 2.4.0.

**Architecture:** `run sparse` always operates on the original `v0_object` RGB frames so camera registration can use the full scene. `run mesh` consumes that baseline sparse model, stages SAM2 masks into OpenMVS's required `<image-name>.mask.png` naming, passes `--mask-path` / `--ignore-mask-label 0` to DensifyPointCloud, and passes `--ignore-mask-label 0` to TextureMesh while writing all object-isolated outputs under `v0_object_masked`. A central command registry drives CLI help, Chinese annotations, tool requirements, and README synchronization tests.

**Tech Stack:** Python 3.9 main runtime, Python 3.11 SAM2 runtime, COLMAP 4.1.1, OpenMVS 2.4.0, Blender 5.1, unittest.

## Global Constraints

- Canonical commands only: `doctor`, `run extract|mask|sparse|mesh|glb`, `view masks|sparse|mesh|glb`.
- Legacy flat commands are rejected and print the replacement canonical command.
- Every canonical command prints a Chinese description, input, output, and next-step hint before execution.
- Root `README.md` is the authoritative CLI guide and must contain every canonical command.
- Original RGB frames are never replaced by blacked-out or alpha-masked frames.
- COLMAP sparse reconstruction uses original RGB without SAM2 feature masks in the production route.
- OpenMVS object reconstruction uses SAM2 masks; background label `0` is ignored.
- OpenMVS mask files are staged as `<original image filename>.mask.png`.
- Object-isolated OpenMVS/Blender outputs stay in `workspace/runs/v0_object_masked`; baseline sparse data stays in `workspace/runs/v0_object`.
- Existing runtime/config/workspace separation remains unchanged.

---

### Task 1: Canonical CLI registry and parser

**Files:**
- Create: `pipeline/cli_commands.py`
- Modify: `app.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces `parse_command(argv)`, `command_spec(key)`, `print_command_annotation(spec)`, and canonical command metadata.
- `app.main()` consumes the parsed command key and routes to existing stage functions.

- [ ] Write tests proving canonical parsing, old-command rejection, Chinese annotations, and tool requirements.
- [ ] Run focused tests and confirm RED.
- [ ] Implement registry/parser and route `app.py` through it.
- [ ] Run focused tests and confirm GREEN.

### Task 2: README as tested CLI contract

**Files:**
- Create: `README.md`
- Modify: `tests/test_cli.py`

**Interfaces:**
- README contains each command returned by `canonical_command_lines()`.

- [ ] Add failing test that every canonical command line appears in root README.
- [ ] Run focused test and confirm RED.
- [ ] Write README with Chinese command guide, workflow, workspace layout, resume behavior, and V0.7 notes.
- [ ] Run focused test and confirm GREEN.

### Task 3: OpenMVS mask staging and exact v2.4.0 arguments

**Files:**
- Modify: `pipeline/segmentation.py`
- Modify: `pipeline/openmvs.py`
- Modify: `tests/test_segmentation.py`
- Modify: `tests/test_openmvs.py`

**Interfaces:**
- Add `prepare_openmvs_masks(frames_dir, masks_dir, output_dir) -> dict`.
- `build_densify_args(openmvs_dir, safe_mode=False, mask_path=None)` adds `--mask-path <dir> --ignore-mask-label 0` when mask path is supplied.
- `build_texture_mesh_args(openmvs_dir, masked=False)` adds `--ignore-mask-label 0` in masked mode.
- `run_mesh_pipeline(..., mask_path=None)` propagates mask settings through normal and safe densify attempts and TextureMesh.

- [ ] Add failing tests for `.mask.png` staging, Densify mask flags, safe retry mask flags, and TextureMesh mask filtering.
- [ ] Run focused tests and confirm RED.
- [ ] Implement minimal mask-aware behavior.
- [ ] Run focused tests and confirm GREEN.

### Task 4: Production data flow: original SfM + masked MVS

**Files:**
- Modify: `app.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- `run sparse` resolves only `workspace/runs/v0_object`.
- `run mesh` reads baseline frames/sparse model, validates SAM2 masks, stages OpenMVS masks, and writes to `v0_object_masked/openmvs`.
- `run glb`, `view mesh`, and `view glb` read the masked object workspace.
- `view sparse` always reads baseline sparse output.

- [ ] Add failing route tests for baseline sparse and masked mesh output separation.
- [ ] Run focused tests and confirm RED.
- [ ] Implement route changes.
- [ ] Run focused tests and confirm GREEN.

### Task 5: Viewer project.ini isolation

**Files:**
- Modify: `pipeline/colmap.py`
- Modify: `tests/test_colmap.py`

**Interfaces:**
- Add `prepare_gui_model(model_path, viewer_model_path)` that copies only `cameras.bin`, `images.bin`, `points3D.bin`.
- `launch_colmap_gui` imports the clean viewer model, preventing mapper-specific `project.ini` keys from being auto-loaded with the reconstruction.

- [ ] Add failing test for clean viewer-model staging.
- [ ] Run focused test and confirm RED.
- [ ] Implement staging and use it in GUI launch.
- [ ] Run focused tests and confirm GREEN.

### Task 6: Full verification and packaging

**Files:**
- Create: `README_V07_PATCH.txt`
- Package: `Videoto3D_v07_cli_mask_openmvs_patch.zip`

- [ ] Run `python -m unittest discover -s tests -v` and require zero failures.
- [ ] Run `python -m compileall app.py pipeline scripts tests` and require exit code 0.
- [ ] Run parser smoke tests for all canonical commands without invoking external binaries.
- [ ] Package only files that must overwrite/add into the project root.
- [ ] Extract ZIP onto a fresh copy of the V0.6 Patch 2 tree and repeat the full test suite.

---

## Implementation Status (2026-08-16)

Implemented in the V0.7 patch worktree copy:
- Canonical `run` / `view` CLI and legacy-command rejection.
- Chinese command annotations and root README contract test.
- Original-RGB COLMAP sparse + SAM2-mask OpenMVS production routing.
- OpenMVS `.mask.png` staging, Densify mask flags, TextureMesh ignore-label flag.
- Conservative Windows Densify retry (single thread on high-core target machines).
- Stage-level OpenMVS resume/cache with downstream invalidation.
- Cache invalidation after new extracted frames, masks, or sparse camera solution.
- Clean COLMAP GUI import model without mapper `project.ini`.
- V0.6 patch notes archived to redirect users to root README.
