# Turntable R0.3b Robust Multi-Baseline Graph Design

## Goal

Make long-baseline Turntable constraints usable without letting a small number
of poor long-baseline correspondences dominate the free-span trajectory.

R0.3a demonstrated that gaps {1,2,3} improve the reliable solution, while the
equal-family gap-5 graph can drive the optimizer toward a pathological local
trajectory even though its objective decreases monotonically.

## Evidence motivating the change

On `chair_nonuniform_280`:

- A gap {1}: span error 3.63 deg, angle MAE 2.31 deg.
- C gap {1,2,3}: span error 2.29 deg, angle MAE 1.57 deg.
- D gap {1,2,3,5}: span error 1.17 deg but angle MAE 9.93 deg,
  increment MAE 1.45 deg, axis/orbit errors above 1 deg, and a pathological
  delta sequence containing near-zero increments followed by very large jumps.
- D's accepted objective decreases monotonically, so the optimizer is obeying
  its objective; the graph/objective is the failing component.

With equal-family weighting, each of 11 gap-5 edges receives about 5.4x the
weight of one of 59 adjacent edges.

## Architecture

R0.3b adds a new robust layer without changing R0.3a or earlier math:

1. Run the reliable gap {1,2,3} solution as a GT-free anchor.
2. Diagnose every candidate graph edge against that anchor.
3. Gate unsupported long-baseline edges using robust statistics derived from
   trusted gap <= 3 edges.
4. Compare fixed weighting strategies:
   - equal_edge
   - equal_family
   - sqrt_family
   - confidence_weighted
5. Optimize accepted graph edges with fixed weights and the same monotonic
   best-state semantics.
6. Optionally add a very weak robust second-difference trajectory penalty as a
   separate ablation. No span prior is introduced.

## Edge diagnostics

For each edge `(i,j)` record:

- gap
- raw match count
- anchor trajectory angle `theta_j - theta_i`
- trimmed-RMS Sampson residual at the anchor angle
- locally best structured angle in a bounded window around the anchor angle
- best trimmed-RMS Sampson residual
- absolute angle disagreement
- residual ratio `anchor_residual / best_residual`

All diagnostics use only image correspondences, camera intrinsics, and the
GT-free anchor state.

## Robust long-baseline gating

Gap <= 3 edges are trusted and retained.

For gap > 3, derive adaptive thresholds from trusted-edge diagnostics using
median/MAD and robust quantiles. A long edge is accepted only if both:

- anchor residual is compatible with trusted-edge residual distribution; and
- pair-specific best angle is compatible with the anchor summed angle.

The report must preserve every rejected edge and its rejection reason.

## Weighting strategies

`equal_edge`:
Every accepted edge has equal mass.

`equal_family`:
Every enabled gap family has equal total mass. This reproduces the R0.3a
behavior and is retained only as a baseline.

`sqrt_family`:
Gap-family total mass is proportional to sqrt(edge_count), between equal-edge
and equal-family extremes.

`confidence_weighted`:
Start from sqrt-family base weights and multiply by a fixed confidence derived
from anchor diagnostics. Normalize once before optimization. Weights remain
fixed during optimization so the solver cannot game its own confidence.

## Optional weak trajectory regularity

A robust Huber penalty on second differences of adjacent increments can be
enabled with a small weight. It discourages pathological redistributions such
as near-zero increments followed by very large jumps, but it does not constrain
total span and must be evaluated as a separate configuration.

Default R0.3b promotion does not require regularity to pass.

## Benchmark structure

Stage 1:
- `A_adjacent`: frozen R0.2b-2.1 baseline.
- `B_gap123_anchor`: R0.3a gaps {1,2,3}; this is the GT-free anchor.

Stage 2:
All gap-5 treatment variants start from the same `B_gap123_anchor` state:

- `C_gap1235_equal_family_raw`
- `D_gap1235_equal_edge`
- `E_gap1235_sqrt_family`
- `F_gap1235_gated_confidence`
- optional `G_gap1235_gated_confidence_regularized`

This isolates the effect of gap-5 treatment rather than changing the
initializer.

## Promotion gate

R0.3b passes if a robust gap-5 configuration:

- improves span error relative to B;
- does not worsen angle MAE relative to B by more than 0.10 deg;
- axis error < 1 deg;
- orbit-line error < 1 deg;
- increment MAE < 0.15 deg;
- span error < 2 deg;
- angle MAE < 2 deg;
- monotonicity violations = 0;
- best state returned = true;
- accepted objective history is non-increasing.

Ground truth remains evaluation-only.

## Scope boundaries

Do not modify:
- R0.2a `structured_fit.py`
- R0.2b-1 `shared_geometry.py`
- R0.2b-2.1 `joint_refine.py`
- R0.3a `multibaseline.py`
- Orbit Camera
- frozen `legacy_v13`
- OpenMVS / Blender / GLB / Gaussian production paths
- BUG-0014 behavior

Create:
- `pipeline/workflows/turntable/pose/robust_multibaseline.py`
- `tools/turntable_r03b_robust_ab_benchmark.py`
- `tests/test_turntable_research_r03b_robust.py`
- `tests/test_turntable_research_r03b_entrypoint.py`
- `docs/research/turntable/Turntable_R0.3b_RobustGraph.md`
