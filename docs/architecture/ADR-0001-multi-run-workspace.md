# ADR-0001: Multi-Run Workspace

- Status: Accepted
- Version: V0.8
- Date: 2026-08-16

## Context

V0.7 used fixed `v0_object` / `v0_object_masked` directories. That was sufficient for a single validation object but cannot safely manage multiple assets.

## Decision

Every reconstruction task owns one directory:

`workspace/runs/<run_id>/`

The run contains source, frames, masks, COLMAP, OpenMVS, output, logs and a machine-readable `run.json` manifest.

Canonical CLI operations identify a task with `--run <run_id>`. Asset viewers for OBJ/GLB additionally accept `--path` for arbitrary files.

## Consequences

- Runs never overwrite one another.
- The CLI and future Web GUI share the same run manifest.
- Pipeline stages can be resumed from run-local caches.
- Legacy fixed V0.7 workspace paths are no longer used.
