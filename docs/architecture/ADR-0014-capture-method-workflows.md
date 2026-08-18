# ADR-0014 · Capture-method workflows

## Status
Accepted for Videoto3D V1.4.

## Decision
Videoto3D routes each Run by the physical capture method selected at Run creation:

- `orbit_camera`: object fixed, camera moves. Stable full-RGB incremental SfM.
- `turntable`: camera fixed, rigid object rotates. Independent research workflow.

No A/B naming is used in code, manifest, UI, or README.

`capture_mode` remains the persistent Run identifier and becomes immutable after source import/extraction.

## Stable Orbit Camera boundary
`pipeline/colmap.py` remains shared low-level COLMAP infrastructure. The Orbit workflow always invokes it with `mask_path=None`, preserving the validated full-RGB incremental SfM behavior.

## Turntable boundary
V1.3 Turntable pose/angle code is frozen under `pipeline/workflows/turntable/legacy_v13/`. New structured-essential, cycle-consistent/global-orbit and future SfM-free Gaussian work is implemented only inside Turntable.

## UI
New Run continues to collect Video + Run ID + Capture Method in one modal. `RunDetailPage.tsx` becomes a capture-method router with separate Orbit Camera and Turntable views.

## Consequences
- Turntable research cannot silently change Orbit Camera pose recovery.
- Existing Runs remain compatible because the canonical capture IDs already exist.
- GLB and PLY remain common output formats while Turntable upstream algorithms can evolve independently.

## Test contract migration

V1.4 contract tests inspect behavior at the workflow boundary. Tests that previously scanned `pipeline/turntable.py`, `pipeline/turntable_angle.py`, or required viewer components directly inside `RunDetailPage.tsx` are updated to inspect the new capture-specific modules. Compatibility shims are not treated as canonical implementations.
