# ADR-0011 — Turntable uses uniform known poses before triangulation

- **Status:** Accepted
- **Date:** 2026-08-17
- **Version:** V1.3.1

## Context

V1.3 introduced manual Turntable capture and used SAM2 masks to stop the fixed background from dominating COLMAP features. Real reconstruction showed that masking alone did not constrain the camera trajectory enough: Mesh was incomplete/deformed and Gaussian Splat developed severe ghosting and elongated splats.

## Decision

Orbit Camera keeps the existing incremental COLMAP mapper.

Turntable no longer asks the mapper to infer free camera poses. The recording is treated as one uniformly sampled full rotation. Videoto3D writes deterministic equivalent virtual camera poses for both rotation signs and uses COLMAP `point_triangulator` to triangulate matched subject features from those registered poses. The stronger candidate becomes the Shared sparse model.

## Consequences

- Both Mesh and Splat continue to consume the same `colmap/sparse/0`.
- Turntable requires a stricter capture contract: one full roughly uniform rotation, fixed camera, rigid subject, approximately level view.
- Reconstruction scale remains arbitrary.
- Non-uniform turntable motion is not solved in this version.
