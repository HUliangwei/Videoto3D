# Turntable R0.2b-1 Shared Observable Geometry Design

## Goal

Recover the shared Turntable rotation axis and the epipolar-observable
transverse orbit direction from image correspondences while signed
relative angles are supplied by the synthetic benchmark.

## Estimator boundary

Inputs:
- masked image correspondences;
- camera intrinsics;
- signed relative angle for each selected synthetic pair.

Not inputs:
- ground-truth shared rotation axis;
- ground-truth orbit vector.

GT shared geometry is loaded only after optimization for metrics.

## Observable parameterization

If `v = v_perp + lambda a` and `R a = a`, then

`v - Rv = v_perp - R v_perp`.

The axial orbit component is unobservable. Essential matrices are also
scale-free, so the magnitude of `v_perp` is unobservable.

Solve for:
- unit rotation axis `a`;
- unit transverse orbit direction `u`;
- `a dot u = 0`.

Represent them by `Q = [u, a x u, a]` in SO(3), which has 3 DOF.
`u` and `-u` are gauge-equivalent because they only flip the sign of E.

## Objective

For each pair `(i,j)` with known signed synthetic delta:

`E_ij(a,u) = [u - R(a,delta_ij)u]_x R(a,delta_ij)`.

Minimize a trimmed RMS Sampson residual across multiple pairs. Use a
deterministic SO(3) Euler grid for global initialization, keep several
best seeds, then refine the entire observable frame by small rotations.

## Research attribution

Kosaka et al., CVPRW 2026 publicly motivates shared-axis,
structured-Essential and global-orbit refinement. The exact 3-DOF
observable-frame parameterization and deterministic optimizer here are
Videoto3D research choices, not claimed as a verbatim paper reproduction.

## Non-goals

R0.2b-1 does not modify Orbit Camera, frozen `legacy_v13`, production
Sparse, GLB, PLY, OpenMVS, or Brush reconstruction math.
