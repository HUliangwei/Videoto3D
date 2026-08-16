# ADR-0005: GUI Control / Viewer Boundary
> **V1.1 note:** the V1.0 read-only limitation is superseded by ADR-0007. The control/viewer module boundary defined here remains in force.

**Status:** Accepted  
**Version:** V1.0

## Context

Videoto3D already has a stable Python reconstruction core and two output routes. The local GUI must not duplicate pipeline logic, and the 3D viewing capability should be reusable in unrelated projects such as a personal website.

## Decision

Create a root-level `gui/` module with two explicit boundaries:

- `gui/control`: Videoto3D-specific Studio UI and read-only local API bridge.
- `gui/viewer`: generic 3D asset viewer with no knowledge of runs, workspace paths, reconstruction tools, or API endpoints.

The Core never imports GUI modules except the top-level `app.py gui` launcher. Reconstruction stages remain authoritative in `pipeline/`.

V1.0 is read-only. The server may read `run.json`, `quality/report.json`, and known final asset paths, but does not run routes or mutate reconstruction state.

## Viewer implementation

- GLB: Three.js `GLTFLoader`.
- Gaussian Splat PLY: Spark renderer.
- Shared shell: camera orbit, framing/reset, fullscreen, loading/error state.

The public viewer interface is `type + src`, allowing the module to move to a portfolio site without Videoto3D dependencies.

## Consequences

- GUI can evolve independently from the core.
- CLI remains a complete advanced interface.
- Viewer can be migrated/repackaged independently.
- V1.1 can add control endpoints without changing viewer contracts.
