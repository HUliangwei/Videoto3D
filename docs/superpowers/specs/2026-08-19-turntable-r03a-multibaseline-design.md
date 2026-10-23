# Turntable R0.3a Multi-Baseline Structured Constraints Design

## Goal
Reduce the residual global angular-scale drift of the stable adjacent-only R0.2b-2.1 solver by adding image-supported multi-baseline constraints, without GT pose, GT span, or a forced 360-degree prior.

## Frozen baseline
R0.2b-2.1 remains the adjacent-only baseline. Its current `chair_nonuniform_280` result is approximately: axis error 0.158 deg, orbit-line error 0.156 deg, increment MAE 0.065 deg, span error 3.63 deg, angle MAE 2.31 deg, monotonicity violations 0, `stable_state`, `best_state_returned=true`.

## Estimator contract
- `ground_truth_axis_used = false`
- `ground_truth_orbit_used = false`
- `ground_truth_angles_used = false`
- `ground_truth_span_used = false`
- `forced_360_degree_span = false`
- `one_direction_monotonic_prior = true`
- camera intrinsics are known synthetic calibration
- GT is evaluation-only

## Observation graph
An edge is `(i, j)` with `j > i`, masked feature correspondences, `gap=j-i`, and a family weight.

A/B configurations:
- A: gaps `{1}`
- B: gaps `{1,2}`
- C: gaps `{1,2,3}`
- D: gaps `{1,2,3,5}`

Gaps 1, 2, 3 use all valid pairs. Gap 5 uses `(0,5),(5,10),(10,15),...`.
Edges with fewer than 8 correspondences are rejected and recorded.

## Global trajectory
Adjacent increments remain the variables:
`delta_k > 0`, `theta_0 = 0`, `theta_t = sum(delta_0 ... delta_{t-1})`.

For edge `(i,j)`:
`DeltaTheta(i,j) = theta_j - theta_i = sum(delta_k, k=i..j-1)`.

No total-span constraint is used.

## Structured geometry
Each edge uses unchanged single-axis structured Essential geometry:
`E_ij = E(a, u, DeltaTheta(i,j))`.

Do not modify R0.2a `structured_fit.py` or R0.2b-1 `shared_geometry.py`.

## Multi-baseline joint objective
For each edge compute trimmed mean Sampson squared residual. Combine edges with equal total weight per enabled gap family:
`J_graph = median_focal * sqrt(weighted_mean(edge_trimmed_mean_sampson_sq))`.

Within each gap family, accepted edges split that family's weight equally. Family totals are normalized globally.

## Solver
Reuse R0.2b-2.1 acceptance semantics:
1. trajectory proposal;
2. shared-geometry proposal;
3. score the same full graph objective;
4. accept only if `J_graph` improves;
5. retain best state;
6. stop by stable-state, objective-patience, or max-iterations.

Trajectory refinement is deterministic coordinate descent on adjacent `delta_k`. A candidate `delta_k` is scored through every graph edge spanning that increment. This is the mechanism that exposes accumulated scale bias. No SciPy dependency is added.

Shared-geometry proposals convert selected graph edges into the existing R0.2b-1 prepared-pair schema using the current summed `DeltaTheta(i,j)`.

## A/B benchmark
One command runs A/B/C/D from the same GT-free initializer and the same cached feature observations.

Report per configuration:
- enabled gaps
- attempted/accepted edges and counts by gap
- runtime
- predicted axis, transverse direction, span
- convergence, termination, best-state, objective
- axis error, orbit-line error, angle MAE, increment MAE, span error, monotonicity violations

GT metrics are computed only after all optimization runs finish.

## Promotion gate
At least one of B/C/D must:
- improve both span error and angle MAE relative to A;
- axis error < 1 deg;
- orbit-line error < 1 deg;
- increment MAE < 0.15 deg;
- span error < 2 deg;
- angle MAE < 2 deg;
- monotonicity violations = 0;
- best_state_returned = true;
- accepted objective history non-increasing.

## Scope boundaries
Do not modify Orbit Camera, frozen `legacy_v13`, OpenMVS/Blender/GLB routes, Gaussian/Brush math, or BUG-0014 behavior.

## Planned files
Create:
- `pipeline/workflows/turntable/observations/graph.py`
- `pipeline/workflows/turntable/pose/multibaseline.py`
- `tools/turntable_r03a_ab_benchmark.py`
- `tests/test_turntable_research_r03a_graph.py`
- `tests/test_turntable_research_r03a_solver.py`
- `tests/test_turntable_research_r03a_entrypoint.py`
- `docs/research/turntable/Turntable_R0.3a_MultiBaseline.md`

Update exports only where needed in observation/pose `__init__.py`.
