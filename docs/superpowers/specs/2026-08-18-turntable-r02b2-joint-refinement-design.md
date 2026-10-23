# Turntable R0.2b-2 Joint Alternating Refinement Design

## Goal

Recover the complete synthetic Turntable pose trajectory without using
ground-truth axis, orbit, frame angles, total span, or a forced 360-degree
prior.

The stage remains pose-only research. It does not enter known-pose
triangulation, OpenMVS, GLB, Gaussian Splatting, Orbit Camera, or frozen
`legacy_v13`.

## Validated foundations reused unchanged

R0.2a established that, with correct shared geometry, the structured
Essential family recovers non-uniform adjacent angles accurately.

R0.2b-1 established that, with correct signed adjacent angles, multiple
image pairs recover one shared axis and one epipolar-observable
transverse orbit direction accurately.

R0.2b-2 composes these two capabilities; it does not alter their math.

## Estimator input contract

```text
ground_truth_axis_used          = false
ground_truth_orbit_used         = false
ground_truth_angles_used        = false
ground_truth_span_used          = false
forced_360_degree_span          = false
one_direction_monotonic_prior   = true
```

Camera intrinsics remain known synthetic calibration.

## GT-free initialization

Each adjacent masked-image pair receives a generic Essential-matrix
estimate with RANSAC and pose recovery. No Turntable-specific GT is used.

A candidate is accepted only if its recovered rotation magnitude is in the
adjacent-motion range. 180-degree and otherwise implausible solutions are
rejected rather than allowed to dominate initialization.

Accepted pair rotations provide:
- initial positive adjacent angle magnitudes;
- Rodrigues-axis line candidates;
- transverse orbit-direction line candidates through
  `(I - R)^+ t`.

Shared axis and transverse direction are robustly aggregated as weighted
unoriented lines. Pair weight scales with pose inliers and
`sin(delta)^2`, reducing the influence of weak very-small-angle pose
hypotheses.

Failed pair angles use the median accepted adjacent angle. This is a local
fallback only; it never normalizes the sequence to 360 degrees.

## Alternating solver

The iteration is intentionally angle-first:

```text
generic Essential initialization
          |
          v
    approximate a, u, delta_i
          |
          v
[A] positive structured angle fit
    a,u fixed -> all delta_i
          |
          v
[G] global shared geometry fit
    delta_i fixed -> shared a,u
          |
          v
[A] positive structured angle re-fit
          |
          +---- repeat until tolerance/max iterations
```

Angle-first ordering is deliberate. The R0.2b-1 geometry solver is more
sensitive to badly scaled pair angles than the R0.2a angle solver is to a
modest shared-frame error. Generic Essential initialization provides an
approximate frame, so the first structured angle pass improves the scale
before global geometry estimation.

## Free-span monotonic model

R0.2b-2 currently assumes one-direction Turntable capture:

```text
delta_i > 0
theta_0 = 0
theta_t = sum(delta_i, i < t)
```

There is no constraint on `sum(delta_i)`. A 280-degree sequence is allowed
to remain 280 degrees; a 360-degree sequence may emerge only from evidence.

Reverse-motion capture is out of scope for R0.2b-2.

## Metrics

Ground truth is loaded only after optimization for:
- axis line error;
- axis directed error;
- transverse orbit line error;
- angle MAE;
- increment MAE;
- span error;
- monotonicity violations;
- convergence history.

The report also compares the generic-Essential initialization against the
final joint refinement to expose whether alternating optimization helped.

## Research attribution

Kosaka et al. (CVPRW 2026) motivates shared-axis constrained Essential
geometry and global orbit refinement. The exact generic-Essential
initializer, weighted observable-frame aggregation, positive free-span
parameterization, and alternating schedule here are Videoto3D research
design choices and are not claimed as verbatim paper reproduction.
