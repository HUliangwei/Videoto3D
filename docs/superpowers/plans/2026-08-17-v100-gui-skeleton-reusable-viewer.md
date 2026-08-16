# Videoto3D V1.0 GUI Skeleton + Reusable Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a root-level GUI module that provides a read-only local Videoto3D Studio plus a reusable GLB/Gaussian-Splat viewer module without coupling the reconstruction core to the GUI.

**Architecture:** Keep the Python core authoritative. `gui/control/server` exposes read-only run/quality/asset APIs and serves a built React app. `gui/control/web` renders Runs and Run Detail pages. `gui/viewer` is a standalone Three.js viewer package that knows only `type + src`, using GLTFLoader for GLB and Spark for Gaussian PLY.

**Tech Stack:** Python 3.9+, FastAPI, Uvicorn, React 18, TypeScript, Vite, Three.js 0.180+, Spark 2.1.

## Global Constraints

- Existing `pipeline/` reconstruction behavior must not be reimplemented in the GUI.
- V1.0 is read-only: no New Run, SAM2 ROI, route execution buttons, or live process control.
- `gui/viewer` must not import Videoto3D run/workspace/API concepts.
- Existing CLI remains available; add only `python app.py gui` for this version.
- GLB and cleaned Splat PLY assets are served only from validated run manifests/known output paths.
- Root README and GUI documentation must be updated with every GUI CLI change.

---

### Task 1: Read-only GUI service API
**Files:** Create `gui/control/server/service.py`, `gui/control/server/app.py`, `gui/control/server/requirements.txt`; test `tests/test_gui_server.py`.

- [ ] Write failing tests for run list, run detail, quality data, and safe asset resolution.
- [ ] Implement pure service functions first, then FastAPI routes.
- [ ] Verify API only exposes files inside the selected run and returns 404 for unavailable assets.

### Task 2: Reusable viewer module
**Files:** Create `gui/viewer/package.json`, `gui/viewer/src/AssetViewer.tsx`, `gui/viewer/src/index.ts`, `gui/viewer/README.md`, `gui/viewer/demo/*`.

- [ ] Define `AssetViewer({type:'glb'|'splat', src})` with no Videoto3D imports.
- [ ] GLB renderer uses Three.js GLTFLoader and material-aware lighting.
- [ ] Splat renderer uses `@sparkjsdev/spark` and supports PLY URLs.
- [ ] Add orbit, reset camera, fullscreen, loading/error states.

### Task 3: Read-only Studio frontend
**Files:** Create `gui/package.json`, `gui/control/web/*`.

- [ ] Build Runs page with Shared / Mesh Route / Splat Route cards.
- [ ] Build Run Detail page with status, Quality Report metrics, and Mesh/Splat viewer switch.
- [ ] Use the reusable `gui/viewer` package for both result viewers.
- [ ] Keep About-Sen-inspired layered dark visual language without copying personal assets/content.

### Task 4: CLI launcher
**Files:** Modify `pipeline/cli_commands.py`, `app.py`; create `gui/control/server/launcher.py`; test `tests/test_gui_cli.py`.

- [ ] Add canonical `python app.py gui` command and Chinese annotation.
- [ ] Validate Python GUI dependencies and built frontend.
- [ ] Launch local Uvicorn server and browser; server intentionally stays attached until Ctrl+C.

### Task 5: Docs and verification
**Files:** Modify `README.md`; create `gui/README.md`, `docs/architecture/ADR-0005-gui-control-viewer-boundary.md`, `README_V100_PATCH.txt`; tests `tests/test_docs.py`.

- [ ] Document Control vs Viewer boundaries and local setup/build commands.
- [ ] Document Spark as Viewer implementation detail, not a Core dependency.
- [ ] Run Python full test suite and compileall.
- [ ] Run npm install/build/typecheck for GUI.
- [ ] Fresh-overlay V0.11 + V1.0 ZIP and rerun all verification.
