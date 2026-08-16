# ADR-0009: Pipeline Artifact Inspector

## Status

Accepted — 2026-08-17

## Context

Videoto3D V1.1.2 exposes final GLB/PLY results and quality metrics, but most intermediate outputs remain visible only through the filesystem or external viewers. This makes the Local Web Studio harder to use as a learning/debugging surface and makes recording a convincing GitHub workflow demo unnecessarily manual.

## Decision

Add a read-only Artifact Inspector in `gui/control` and extend `gui/viewer` only with generic PLY point-cloud and PLY mesh rendering.

The control layer owns knowledge of:

- frames and SAM2 masks;
- COLMAP sparse model layout;
- OpenMVS filenames;
- Brush staging/raw/final files;
- run manifests and workspace paths.

The reusable viewer owns only generic asset rendering:

- GLB;
- Gaussian Splat PLY;
- ordinary point-cloud PLY;
- ordinary mesh PLY.

COLMAP sparse binaries are converted to a PLY response on demand by the control server. The inspector never writes to reconstruction outputs and never launches reconstruction jobs.

## Consequences

- A bad stage can be localized visually before checking later stages.
- README/demo capture can show a continuous input → intermediate → final chain.
- The portable viewer remains usable outside Videoto3D.
- Camera frustum visualization is deliberately deferred; V1.2.0 shows COLMAP points and related quality metrics without introducing a second scene-format API.
