# ADR-0003: Flat Run Layout with Shared + Mesh/Splat Route State

- Status: Accepted
- Date: 2026-08-16
- Version: Videoto3D V0.10

## Context

V0.9 proved both Textured Mesh/GLB and Gaussian Splat/PLY routes, but route-private folders were mixed at the Run root and progress was represented as one flat stage list. Brush also inherited background COLMAP points as Gaussian initialization, causing strong target quality with cluttered environment splats.

## Decision

Keep physical Run layout flat: shared `frames/`, `masks/`, `segmentation/`, `colmap/` remain at root; private route intermediates live under `mesh/` and `splat/`; final assets share `output/`. Manifest schema v3 models progress as `shared` plus `routes.mesh` and `routes.splat`.

Add `route mesh` and `route splat` as orchestrators over existing fine-grained `run` functions. Do not duplicate pipeline implementations.

For Splat isolation, preserve the complete RGB COLMAP cameras and filter only `points3D.bin` using each point's multi-view 2D observations against SAM2 masks. Keep staged images consistent by replacing removed point references with `-1`.

## Consequences

- A Run is easy to inspect in Explorer and maps naturally to future GUI cards.
- Shared SfM remains stable and reusable by both routes.
- Splat background contamination is attacked at initialization rather than by reducing camera registration.
- V0.9 Splat outputs are preserved as legacy baselines but V0.10 marks Splat progress pending until object-only retraining completes.
