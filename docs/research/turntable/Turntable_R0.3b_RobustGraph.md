# Turntable R0.3b Robust Multi-Baseline Graph

## Status

Implementation overlay prepared. Real `chair_nonuniform_280` R0.3b A/B benchmark
is pending on the target Windows repository.

## R0.3a evidence

The R0.3a benchmark established two facts:

1. Gaps {1,2,3} are useful:
   - span error: 3.63 deg -> 2.29 deg
   - angle MAE: 2.31 deg -> 1.57 deg
   - increment MAE: 0.065 deg -> 0.051 deg
   - axis/orbit errors remain about 0.10 deg

2. Raw equal-family gap-5 is unstable:
   - span error happened to improve to about 1.17 deg
   - angle MAE degraded to about 9.93 deg
   - increment MAE degraded to about 1.45 deg
   - axis/orbit errors exceeded 1 deg
   - the trajectory developed near-zero increments followed by very large jumps
   - the accepted objective still decreased monotonically

Therefore the R0.3a optimizer was obeying a graph objective whose long-baseline
contribution was not robust enough.

## R0.3b changes

R0.3b keeps all previous math frozen and adds:

- per-edge diagnostics against the GT-free gap {1,2,3} anchor;
- adaptive long-baseline gating from trusted-edge median/MAD statistics;
- fixed graph weighting strategies:
  - `equal_edge`
  - `equal_family`
  - `sqrt_family`
  - `confidence_weighted`
- a fixed-weight robust alternating solver;
- an optional weak Huber second-difference trajectory regularity ablation.

No GT axis/orbit/angle/span is used by estimation or gating.

## Benchmark configurations

```text
A_adjacent
B_gap123_anchor
C_gap1235_equal_family_raw
D_gap1235_equal_edge
E_gap1235_sqrt_family
F_gap1235_gated_confidence
G_gap1235_gated_confidence_regularized   # only when enabled
```

C/D/E/F all start from the same GT-free B anchor state, so the experiment
isolates gap-5 treatment instead of changing initialization.

## Promotion gate

A robust gap-5 configuration must:

- improve span error relative to B;
- worsen B's angle MAE by no more than 0.10 deg;
- axis error < 1 deg;
- orbit error < 1 deg;
- increment MAE < 0.15 deg;
- span error < 2 deg;
- angle MAE < 2 deg;
- monotonicity violations = 0;
- return best state;
- keep accepted objective history non-increasing.

## Scope

R0.3b does not modify:

- R0.2a `structured_fit.py`
- R0.2b-1 `shared_geometry.py`
- R0.2b-2.1 `joint_refine.py`
- R0.3a `multibaseline.py`
- Orbit Camera
- frozen `legacy_v13`
- OpenMVS / Blender / GLB / Gaussian production routes
- BUG-0014 behavior
