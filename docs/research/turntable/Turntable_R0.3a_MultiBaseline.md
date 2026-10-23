# Turntable R0.3a Multi-Baseline Structured Constraints

## Status

Implementation overlay prepared; real `chair_nonuniform_280` A/B benchmark is
pending on the target Windows repository.

## Frozen baseline

R0.2b-2.1 is the stable adjacent-only reference.

Latest measured baseline:

```text
axis line error             0.1575 deg
transverse orbit line error 0.1559 deg
increment MAE               0.0650 deg
span error                  3.63 deg
angle MAE                   2.31 deg
monotonic violations        0
termination                 stable_state
best_state_returned         true
```

The remaining problem is small same-direction adjacent-angle bias accumulating
over the sequence.

Configuration `A_adjacent` is not a reimplementation: a pure gap-1 graph delegates directly to the frozen R0.2b-2.1 `alternating_joint_refinement`, and an automated equivalence regression checks identical state/objective output on synthetic data.

## R0.3a hypothesis

Longer-baseline image edges directly constrain sums of adjacent increments:

```text
DeltaTheta(i,j) = sum(delta_k, k=i..j-1)
```

so scale drift that is weak on one adjacent pair becomes more visible over
gap-2, gap-3 and sparse gap-5 edges.

## A/B configurations

```text
A_adjacent  gaps {1}
B_gap12     gaps {1,2}
C_gap123    gaps {1,2,3}
D_gap1235   gaps {1,2,3,5}
```

All configurations reuse one GT-free initialization and one cached set of image
matches.

## Estimator contract

```text
GT axis used        false
GT orbit used       false
GT angles used      false
GT span used        false
forced 360 deg      false
monotonic prior     true
```

Camera intrinsics remain known synthetic calibration.

## Promotion gate

At least one of B/C/D must improve both span error and angle MAE relative to A
and satisfy:

```text
axis error       < 1 deg
orbit error      < 1 deg
increment MAE    < 0.15 deg
span error       < 2 deg
angle MAE        < 2 deg
monotonic        = 0
best state       = true
objective        non-increasing
```

## Scope

R0.3a is pose research only. R0.2a `structured_fit.py`, R0.2b-1
`shared_geometry.py`, Orbit Camera, frozen `legacy_v13`, OpenMVS, Blender,
GLB/PLY production routes, and BUG-0014 behavior are not modified.
