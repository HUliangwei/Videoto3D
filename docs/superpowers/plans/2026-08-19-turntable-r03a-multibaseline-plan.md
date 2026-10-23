# Turntable R0.3a Multi-Baseline Structured Constraints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GT-free multi-baseline Turntable observation graph and stable structured joint optimizer that tests whether longer-baseline image constraints reduce the residual angular-scale drift of the R0.2b-2.1 adjacent-only baseline.

**Architecture:** Build a reusable observation-graph layer, map graph edges to summed adjacent-angle variables, optimize one robust graph objective with R0.2b-2.1 monotonic acceptance/best-state semantics, then run strict A/B configurations `{1}`, `{1,2}`, `{1,2,3}`, `{1,2,3,5}` from one initializer and one observation cache.

**Tech Stack:** Python 3.11, NumPy, OpenCV 4.13 headless, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-turntable-r03a-multibaseline-design.md`

## Global Constraints
- No GT axis/orbit/angles/span in estimation.
- No 360-degree span prior.
- Positive adjacent increments remain the trajectory variables.
- Camera intrinsics are known synthetic calibration.
- Do not modify `structured_fit.py`, `shared_geometry.py`, Orbit Camera, or frozen `legacy_v13`.
- Preserve BUG-0014.
- Do not add SciPy.
- R0.2b-2.1 remains the adjacent-only baseline; a graph containing only gap 1 must delegate to frozen `alternating_joint_refinement`.

---

### Task 1: Observation graph
**Files:** create `pipeline/workflows/turntable/observations/graph.py`; modify observations `__init__.py`; test `tests/test_turntable_research_r03a_graph.py`.

**Produces:** `edge_schedule(frame_count, gaps)` and `build_observation_graph(frame_count, gaps, match_pair, min_correspondences=8)`.

- [ ] Write RED schedule test requiring full gap-1/2/3 edges and sparse stride-5 edges `(0,5),(5,10),...`.
- [ ] Run the single RED test and verify module/function absence.
- [ ] Implement deterministic schedules with positive-gap validation.
- [ ] Write RED acceptance test where one edge has 12 correspondences and one has 6.
- [ ] Implement accepted/rejected graph records with indices, gap, method, raw count, points, and rejection reason.
- [ ] Run `python -m pytest tests/test_turntable_research_r03a_graph.py -q` and require PASS.

### Task 2: Graph trajectory mapping and family weights
**Files:** create `pipeline/workflows/turntable/pose/multibaseline.py`; test `tests/test_turntable_research_r03a_solver.py`.

**Produces:** `cumulative_angles_deg`, `edge_angle_deg`, `prepare_graph_edges`, `graph_gap_weights`.

- [ ] Write RED test: deltas `[2,3,4,5]` must give edge angles `(0,3)=9`, `(1,4)=12`.
- [ ] Implement cumulative/summed angle helpers with finite positive-delta validation.
- [ ] Write RED family-weight test with three gap-1, two gap-2, one gap-5 edges; total weight of each family must match and all weights sum to 1.
- [ ] Implement normalized edge preparation using existing normalized homogeneous coordinates and equal total mass per gap family.
- [ ] Run helper tests and require PASS.

### Task 3: Multi-baseline graph objective
**Files:** modify `pose/multibaseline.py`; test `test_turntable_research_r03a_solver.py`.

**Produces:** `graph_joint_objective_px(...)`.

- [ ] Write RED exact-geometry test comparing true deltas against a uniform 5% scale bias on gap-1/2/3 synthetic edges; true score must be smaller.
- [ ] Implement `E(a,u,theta_j-theta_i)` per edge, trimmed Sampson squared residual, family-weighted RMS, median-focal pixel conversion.
- [ ] Add adjacent-only equivalence regression against R0.2b-2.1 `joint_objective_px` for a pure gap-1 graph.
- [ ] Run solver-objective tests and require PASS.

### Task 4: Trajectory coordinate descent
**Files:** modify `pose/multibaseline.py`; test solver tests.

**Produces:** `refine_graph_trajectory(..., step_schedule_deg=(0.25,0.10,0.05,0.02), max_sweeps_per_step=2)` returning deltas, objective, evaluation count, accepted updates.

- [ ] Write RED synthetic recovery test from 5% scale-biased non-uniform deltas.
- [ ] Implement deterministic per-delta +/- step candidates, positive-delta guard, full-graph scoring, strict-improvement acceptance.
- [ ] Add free-span regression on a short trajectory under 60 degrees and assert it is not normalized to 360.
- [ ] Run trajectory tests and require PASS.

### Task 5: Stable multi-baseline alternating solver
**Files:** modify `pose/multibaseline.py`; update pose `__init__.py`; test solver tests.

**Produces:** `alternating_multibaseline_refinement(...)` with axis, transverse direction, deltas, span, objective, best-state, convergence, termination, iteration count, objective history, detailed history.

- [ ] Write RED end-to-end algebraic test with perturbed axis/u and 5% angle-scale bias.
- [ ] Implement trajectory proposal using Task 4.
- [ ] Implement shared-geometry proposal by selecting graph edges and converting current summed edge angles to unchanged R0.2b-1 prepared-pair schema.
- [ ] Apply one full graph objective for all candidate acceptance.
- [ ] Retain/return best state; keep accepted objective history non-increasing; preserve stable-state/objective-patience/max-iterations termination.
- [ ] Add monotonic-objective and best-state tests.
- [ ] Run solver tests and require PASS.

### Task 6: Strict A/B benchmark
**Files:** create `tools/turntable_r03a_ab_benchmark.py`; test `tests/test_turntable_research_r03a_entrypoint.py`.

**Produces:** `workspace/research/turntable/r03a/<dataset>/r03a_ab_report.json`.

- [ ] Write RED direct-entrypoint `--help` test.
- [ ] Implement one-time match cache for union graph D `{1,2,3,5}`.
- [ ] Run the existing GT-free adjacent initializer once and clone the same initial state into all A/B/C/D runs.
- [ ] Run configurations `A_adjacent=(1,)`, `B_gap12=(1,2)`, `C_gap123=(1,2,3)`, `D_gap1235=(1,2,3,5)` with identical optimizer settings.
- [ ] Load GT only after all four predictions exist.
- [ ] Emit per-config metrics, edge counts, runtime, and comparison summary with evaluation-only `promotion_pass`.
- [ ] Run entrypoint test and require PASS.

### Task 7: Documentation and verification
**Files:** create `docs/research/turntable/Turntable_R0.3a_MultiBaseline.md`.

- [ ] Record `R0.2b-2.1 = frozen adjacent-only baseline`, `R0.3a = multi-baseline graph`, GT pose evaluation-only, no span prior.
- [ ] Run targeted R0.2b-2.1/R0.3a/BUG-0014 tests.
- [ ] Run full `python -m pytest -q` and `git diff --check`.
- [ ] Run real benchmark:
  `.\env\core\python.exe tools/turntable_r03a_ab_benchmark.py --dataset ".\workspace
esearch	urntable\synthetic\chair_nonuniform_280" --max-points 160 --iterations 12 --keep-ratio 0.70 --output-dir ".\workspace
esearch	urntable
03a\chair_nonuniform_280"`
- [ ] Promote only if at least one B/C/D improves both span error and angle MAE over A and meets all spec gates.
- [ ] Commit the checkpoint only after the real benchmark is interpreted accurately.
