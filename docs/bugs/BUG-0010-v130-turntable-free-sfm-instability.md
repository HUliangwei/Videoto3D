# BUG-0010 — V1.3 Turntable mask-guided free SfM produces unstable geometry

- **Status:** Mitigated
- **Severity:** High
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** V1.3.0 Turntable
- **Fixed/Mitigated in:** V1.3.1
- **Upstream:** N/A

## Summary

Turntable V1.3 correctly excluded static background features with SAM2 masks, but still let COLMAP's incremental mapper freely estimate camera motion. Fixed-camera/object-rotation footage remained poorly constrained.

## Symptom

Observed on a real rotating subject:
- textured Mesh retained only a partial/deformed body;
- cleaned Gaussian Splat showed strong ghosting, large translucent blobs, streaks, and displaced appearance.

Both route failures share the same upstream sparse camera geometry.

## Root cause

The capture mode is known to be a fixed camera plus rotating rigid object, but V1.3 only changed feature selection. It did not encode the known rotational motion model. The Shared sparse model could therefore have camera poses that are incompatible with a uniform turntable sequence.

## Fix

V1.3.1 keeps mask-guided features, but replaces free Turntable mapping with:
1. one-full-turn uniform angle assignment;
2. equivalent virtual camera poses;
3. automatic CW/CCW candidate generation;
4. COLMAP known-pose point triangulation;
5. candidate selection by sparse-point support then reprojection error.

Orbit Camera remains unchanged.

## Regression guard

`tests/test_turntable_known_poses.py` validates geometry, database IDs, model serialization, and candidate selection. `tests/test_v131_turntable_contract.py` validates the app branch.

## Verification

Package verification passes isolated geometry tests and synthetic patch application. Real Windows validation requires a new Turntable run through both Mesh and Splat; old V1.3 outputs must not be reused.

## Risks / Trade-offs

This fix intentionally assumes a trimmed, roughly uniform full 360° recording and an approximately vertical turntable axis. It does not model arbitrary non-uniform object motion.

## Timeline

- 2026-08-17 — V1.3 real Turntable Mesh/Splat quality failure observed.
- 2026-08-17 — Shared free-pose Turntable SfM identified as common upstream failure.
- 2026-08-17 — V1.3.1 known-pose strategy prepared.
