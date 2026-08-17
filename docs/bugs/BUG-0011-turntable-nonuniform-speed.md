# BUG-0011 — Uniform Turntable timing distorts non-uniform rotations

- **Status:** Mitigated
- **Severity:** High
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** V1.3.1 Turntable known-pose reconstruction
- **Fixed/Mitigated in:** V1.3.2

## Summary

V1.3.1 mapped frame index directly to equal angular increments. If the subject slowed down or sped up, known camera poses no longer matched the visual motion, contaminating the shared sparse geometry and therefore both Mesh and Splat.

## Root cause

The fixed relationship `theta_i = 2π i/N` assumes constant angular velocity. Real manual turns violate that assumption.

## Fix

V1.3.2 derives adjacent relative-rotation magnitudes from COLMAP verified `two_view_geometries`, robustly smooths them, and integrates them into a monotonic full-turn angle trajectory. Uniform angles remain only as an explicit low-evidence fallback.

## Regression guard

`tests/test_turntable_adaptive_angle.py` validates synthetic essential decomposition, non-uniform speed preservation, missing-pair fallback, and monotonic cumulative angles.

## Verification

Package-level synthetic tests pass. Real validation requires a new Turntable run; previously generated sparse/mesh/splat outputs must not be reused.
