# ADR-0007: Web Control delegates reconstruction to Core CLI

- **Status:** Accepted
- **Version:** V1.1
- **Date:** 2026-08-17

## Context
V1.0 proved the local Web Viewer and read-only run/quality APIs. V1.1 needs write controls without creating a second reconstruction implementation in FastAPI/React.

## Decision
`gui/control` may create run-local source files and manage background jobs, but every reconstruction action launches the existing project-local Core interpreter:

```text
env/core/python.exe -u app.py <canonical command>
```

Browser SAM2 ROI is bridged through `run mask --box x0,y0,x1,y1`; Mesh and Splat buttons call the existing `route mesh` / `route splat` commands. `gui/viewer` remains unaware of runs, routes, COLMAP, OpenMVS, SAM2, or workspace paths.

Only one active GUI job is allowed per Run. Job stdout is streamed into a bounded in-memory buffer and persisted under `logs/gui/`.

## Consequences
- CLI and GUI share all reconstruction and invalidation behavior.
- New algorithm changes continue to happen under `pipeline/` / canonical CLI, not FastAPI.
- The control module is intentionally Videoto3D-specific; the viewer remains portable to other projects.
