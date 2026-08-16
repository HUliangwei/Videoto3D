# V1.1.1 Progress UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every GUI control job visibly report what is running, how far it has progressed when the pipeline exposes reliable evidence, elapsed time, stage status, and live logs without changing reconstruction algorithms.

**Architecture:** Extend `JobManager` with a read-only progress snapshot derived from run-local files, manifests, job command arguments, and emitted log lines. The React control layer renders that snapshot as a sticky progress card and compact top-navigation status while keeping logs collapsed by default. Exact percentages are shown only for measurable work such as SAM2 masks and Brush exports; stage-only jobs use a stepper without fake percentages.

**Tech Stack:** Python 3.11, FastAPI job API, React 18, TypeScript, Vite.

## Global Constraints

- Do not alter SAM2/COLMAP/OpenMVS/Brush reconstruction algorithms.
- Reuse the existing background job process and `/api/jobs/<id>` polling.
- Keep `gui/viewer/` free of Videoto3D control concepts.
- Show exact percentages only from trustworthy counters.
- Keep live logs persisted under the existing run-local GUI log directory.
- Update canonical README for behavior changes.

---

### Task 1: Server-side progress snapshots

**Files:**
- Create: `gui/control/server/progress.py`
- Modify: `gui/control/server/jobs.py`
- Test: `tests/test_gui_progress.py`

**Interfaces:**
- Consumes: run root, job kind, command, current log lines.
- Produces: `build_progress_snapshot(run_root, kind, command, lines, status)` returning JSON-safe progress metadata.

- [ ] Write failing tests for exact SAM2 mask progress, Splat export progress, and stage-only Mesh progress.
- [ ] Run focused tests and confirm RED.
- [ ] Implement minimal progress inference.
- [ ] Add `progress` to public Job API payloads.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Sticky progress UI and compact global status

**Files:**
- Modify: `gui/control/web/src/types.ts`
- Modify: `gui/control/web/src/components/JobPanel.tsx`
- Modify: `gui/control/web/src/App.tsx`
- Modify: `gui/control/web/src/pages/RunDetailPage.tsx`
- Modify: `gui/control/web/src/styles.css`
- Test: `tests/test_gui_frontend_progress_contract.py`

**Interfaces:**
- Consumes: `JobInfo.progress`.
- Produces: sticky progress card, determinate progress bar when available, stage stepper, elapsed time, collapsible live log, success/failure state, and top-nav compact job indicator.

- [ ] Write source-contract tests and confirm RED.
- [ ] Implement UI components with no fake percentages.
- [ ] Keep logs collapsed until requested, auto-open on failure.
- [ ] Run focused tests and confirm GREEN.

### Task 3: Documentation, versioning, and verification

**Files:**
- Modify: `README.md`
- Modify: `pipeline/cli_commands.py`
- Modify: `gui/control/server/app.py`
- Modify: GUI package version files as needed.

- [ ] Document V1.1.1 progress behavior and exact/stage-only rules.
- [ ] Run full Python test suite.
- [ ] Run `compileall`.
- [ ] Run TypeScript/source syntax verification available in the isolated environment.
- [ ] Overlay the patch on a fresh V1.1 baseline and rerun verification.
- [ ] Build a direct-overwrite ZIP.
