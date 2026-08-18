# ADR-0013 — Turntable uses a free-span multi-pair angle graph

- **Status:** Accepted
- **Date:** 2026-08-17
- **Version:** V1.3.3

## Context

V1.3.2 removed the constant-speed requirement, but still estimated only adjacent-pair rotation magnitudes and normalized the cumulative trajectory to nearly 360°. Real low-cost Turntable capture can contain blur, missing adjacent geometry, non-uniform speed, and a clip that covers less or more than one exact turn.

The reliable physical prior is narrower: the camera is fixed, the subject is rigid, and the subject rotates primarily in one direction around one dominant axis.

## Decision

Keep the existing Turntable known-pose → CW/CCW COLMAP point triangulation backend and both downstream Mesh/GLB and Splat/PLY routes unchanged.

Replace only the angle estimator:

1. Read verified temporal pairs from COLMAP `two_view_geometries` across a bounded frame gap.
2. Convert each usable E/F geometry to a relative rotation magnitude.
3. Treat each pair as a 1-D constraint `theta[j] - theta[i] ~= delta_ij`.
4. Solve positive adjacent increments with robust weighted least squares plus weak gap priors.
5. Accumulate the solved increments directly. Do **not** normalize the result to 360°.

A near-complete turn remains a capture recommendation for full surface coverage, not a mathematical requirement for pose generation.

## Consequences

- Non-uniform speed remains supported.
- Missing adjacent pairs can be bridged by non-adjacent verified geometry.
- The estimated total span may be 180°, 270°, 330°, 370°, etc.
- Direction reversal and non-rigid motion remain outside the current capture contract.
- GLB and PLY reconstruction routes keep the same inputs and outputs after sparse reconstruction.
