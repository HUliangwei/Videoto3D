# Turntable R0.3c Anchor-Independent Multi-Hypothesis Pair Estimation

## Goal
Generate several plausible structured relative-angle hypotheses from each image pair without using the current global angle trajectory as the search center. Shared axis/transverse geometry may come from the GT-free gap-{1,2,3} anchor, but per-edge angle candidates must be searched over a fixed broad domain.

## Inputs
- masked image correspondences
- known intrinsics
- GT-free shared axis `a`
- GT-free transverse orbit direction `u`

Not used by candidate generation:
- anchor `theta_i`
- anchor `theta_j`
- GT angles
- GT span
- forced 360-degree prior

## Pair search
For each edge `(i,j)`:
1. Search structured Sampson residual over a fixed angle interval.
2. Detect local minima.
3. Refine each minimum with a finer local step.
4. Keep up to `top_k` minima separated by at least `min_separation_deg`.
5. Report residual and normalized confidence.

Default search:
- min angle: 0.25 deg
- max angle: 60 deg
- coarse step: 0.25 deg
- refine step: 0.05 deg
- top_k: 3
- minimum separation: 0.5 deg

## Fast benchmark
The benchmark can reuse the shared axis/u from an existing R0.3b report via `--r03b-report`, avoiding another full anchor optimization. It matches only requested gaps, generates hypotheses, then loads GT for evaluation.

Primary synthetic metrics:
- top-1 angle error
- top-K oracle angle error
- top-K recall within 0.25 / 0.5 / 1.0 deg
- candidate count
- runtime
- per-gap metrics

## Scope
R0.3c does not modify R0.3a or R0.3b solvers. It only adds pair-hypothesis generation and an evaluation tool. R0.4 will perform cycle-consistent hypothesis selection.
