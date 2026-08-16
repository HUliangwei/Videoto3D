# Videoto3D V1.1 Web Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add browser-side run creation, SAM2 ROI selection, Mesh/Splat control and live job logs while keeping reconstruction in the existing CLI/core.

**Architecture:** FastAPI control endpoints launch `env/core/python.exe app.py` jobs through a focused job manager. The React control app supplies upload, ROI, route buttons and a polling log panel. The reusable viewer remains unchanged except for version metadata.

**Tech Stack:** Python stdlib, FastAPI/Uvicorn, React 18, TypeScript, Vite, Three.js/Spark.

## Global Constraints
- All task data stays under `workspace/runs/<run_id>`.
- GUI control may depend on Videoto3D; `gui/viewer` may not.
- No duplicate reconstruction implementation in the GUI server.
- One active background job per Run.
- Preserve project-local Conda environments and automatic bootstrap.
- TDD before production changes.

---

### Task 1: Browser ROI CLI bridge
**Files:** `pipeline/cli_commands.py`, `app.py`, `tests/test_cli_v11.py`, `tests/test_cli.py`
**Produces:** `run mask --run <id> --box x0,y0,x1,y1` and propagation into existing `run_segmentation(..., box=...)`.
- [ ] Add failing parse/propagation tests.
- [ ] Run focused tests and verify RED.
- [ ] Add one CSV box option and validation.
- [ ] Pass parsed box into `run_mask`.
- [ ] Run focused tests GREEN.

### Task 2: GUI background job manager and lifecycle
**Files:** `gui/control/server/jobs.py`, `gui/control/server/launcher.py`, `tests/test_gui_jobs.py`, `tests/test_gui_cli.py`
**Produces:** process-backed job state/logs and graceful Ctrl+C forwarding.
- [ ] Add failing job/log and Ctrl+C helper tests.
- [ ] Verify RED.
- [ ] Implement bounded log job manager and Windows process group launch.
- [ ] Implement parent wait loop: Ctrl+C -> HTTP shutdown -> fallback terminate.
- [ ] Verify GREEN.

### Task 3: Write-capable control API
**Files:** `gui/control/server/app.py`, `gui/control/server/service.py`, `tests/test_gui_api.py`
**Produces:** upload/extract, first-frame, mask, Mesh/Splat route, job status/cancel endpoints.
- [ ] Add failing API tests with an injected fake job manager.
- [ ] Verify RED.
- [ ] Implement safe streamed source save and endpoint validation.
- [ ] Implement commands that call existing core CLI only.
- [ ] Verify GREEN.

### Task 4: React control workflow
**Files:** `gui/control/web/src/*`, tests/test_gui_frontend_contract.py`
**Produces:** New Run UI, ROI selector, Mesh/Splat controls, live job console.
- [ ] Add source-contract tests and verify RED.
- [ ] Implement upload/new run screen.
- [ ] Implement ROI selector based on natural image coordinates.
- [ ] Implement route controls/Splat parameters and job polling console.
- [ ] Verify contract tests GREEN.

### Task 5: Version/docs/verification
**Files:** package versions, README, GUI README, ADR/bug docs, tests.
- [ ] Update V1.1 command/manual content.
- [ ] Record Ctrl+C lifecycle defect as BUG-0006 and control architecture ADR.
- [ ] Run full Python tests.
- [ ] Run compileall.
- [ ] Run npm typecheck/build if dependency access is available.
- [ ] Fresh-overlay V1.0.2 Hotfix -> V1.1 and rerun verification.
- [ ] Package direct-overlay ZIP and hash it.
