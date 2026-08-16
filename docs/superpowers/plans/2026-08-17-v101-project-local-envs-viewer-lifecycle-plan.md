# Videoto3D V1.0.1 Project-Local Environments + Viewer Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project-local Conda environments for core/seg/gui, automatic lazy setup, improved reusable viewer camera controls, and explicit graceful Studio shutdown.

**Architecture:** A stdlib-only environment manager bootstraps `env/core` before normal imports and lazily provisions `env/seg` and `env/gui`. The GUI server is launched by the GUI interpreter, while the reusable viewer stays independent and gains a common navigation controller. Existing reconstruction code remains shared and unchanged except for runtime resolution.

**Tech Stack:** Python 3.11, Conda prefix environments, FastAPI/Uvicorn, React 18, TypeScript, Three.js OrbitControls, Spark.

## Global Constraints

- Conda is the only external environment prerequisite; do not auto-install Conda.
- All Python environments live under `<project>/env/{core,seg,gui}` and `env/` is not committed.
- `runtime/` remains third-party tools/models/source; `workspace/` remains run data.
- Normal users never need `conda activate`.
- Environment creation is lazy except core bootstrap.
- Repair never touches runtime, workspace, or other environments.
- Viewer remains portable and must not know Videoto3D control concepts.
- Closing a tab must not terminate Studio; only Exit Studio or Ctrl+C does.
- README is canonical and must be updated.

---

### Task 1: Project-local environment manager and core bootstrap

**Files:**
- Create: `bootstrap.py`
- Create: `pipeline/env_manager.py`
- Create: `config/envs/core.yml`
- Create: `config/envs/gui.yml`
- Create: `config/envs/seg.yml`
- Modify: `app.py`
- Modify: `.gitignore` if present / `README.md`
- Test: `tests/test_env_manager.py`
- Test: `tests/test_core_bootstrap.py`

**Interfaces:**
- `environment_prefix(root, name) -> Path`
- `environment_python(root, name) -> Path`
- `ensure_environment(root, name, ...) -> Path`
- `repair_environment(root, name, ...) -> Path`
- `bootstrap_core(root, argv, executable, execv) -> bool`

- [ ] Write tests proving prefix paths, recipe hash/states, Conda discovery failure, environment creation commands and core re-exec behavior.
- [ ] Run focused tests and confirm RED for missing implementation.
- [ ] Implement minimal stdlib-only environment manager and bootstrap.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Segmentation and GUI runtime migration

**Files:**
- Modify: `pipeline/segmentation_runtime.py`
- Modify: `gui/control/server/launcher.py`
- Modify: `app.py`
- Test: `tests/test_segmentation_runtime.py`
- Test: `tests/test_gui_cli.py`
- Test: `tests/test_env_cli.py`

**Interfaces:**
- Segmentation Python is always `<root>/env/seg/python.exe` after lazy ensure.
- GUI server is always executed by `<root>/env/gui/python.exe`.
- CLI adds `env status` and `env repair <name>`.

- [ ] Write failing migration/lazy-runtime/CLI tests.
- [ ] Run focused tests and verify RED.
- [ ] Implement lazy seg/gui ensure plus env engineering commands.
- [ ] Run focused tests and verify GREEN.

### Task 3: Reusable viewer navigation controls

**Files:**
- Modify: `gui/viewer/src/AssetViewer.tsx`
- Modify: `gui/viewer/README.md`
- Test: `tests/test_gui_frontend_contract.py`

**Interfaces:**
- Generic `AssetViewer` continues to accept `type` and `src`.
- Shared navigation functions support fit/reset/six axes/iso/auto-rotate/fullscreen and double-click focus.

- [ ] Add contract tests for controls and portability.
- [ ] Verify RED.
- [ ] Implement shared camera navigation UI and interaction hints.
- [ ] Verify GREEN.

### Task 4: Explicit graceful Studio exit

**Files:**
- Modify: `gui/control/server/app.py`
- Modify: `gui/control/server/launcher.py`
- Modify: `gui/control/web/src/App.tsx`
- Modify: `gui/control/web/src/api.ts`
- Modify: `gui/control/web/src/styles.css`
- Test: `tests/test_gui_api.py`
- Test: `tests/test_gui_frontend_contract.py`

**Interfaces:**
- `POST /api/system/shutdown` sets a server-owned shutdown event/exit flag.
- Control Web exposes `Exit Studio`; ordinary unload has no shutdown behavior.

- [ ] Add failing API/frontend contract tests.
- [ ] Verify RED.
- [ ] Implement shutdown endpoint, launcher watcher and stopped-state UI.
- [ ] Verify GREEN.

### Task 5: Documentation, migration and release verification

**Files:**
- Modify: `README.md`
- Modify: `gui/README.md`
- Create: `README_V101_PATCH.txt`
- Create: `docs/architecture/ADR-0005-project-local-python-environments.md`
- Modify: `.gitignore`/GUI ignore coverage as appropriate
- Test: `tests/test_docs.py`

**Interfaces:**
- README documents first-run automatic provisioning and GUI controls/exit.
- Existing external `videoto3d-seg` and user-site FastAPI are not required after V1.0.1.

- [ ] Add/update documentation contract tests.
- [ ] Verify RED where applicable.
- [ ] Update canonical docs and ADR.
- [ ] Run full Python tests, compileall, TypeScript syntax parse, CLI smoke and fresh V1.0 overlay verification.
- [ ] Build a direct-overlay ZIP and compute SHA256.
