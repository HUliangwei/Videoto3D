# V1.3.5 Turntable Matching A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated Sequential-vs-Exhaustive matching benchmark for V1.3.4 constrained Turntable reconstruction.

**Architecture:** Treat the existing run database as the read-only Sequential baseline. Create a transactionally consistent SQLite copy, clear only match/geometry rows in that copy, run Exhaustive Matching, and evaluate both databases using identical constrained-pose and known-pose triangulation code.

**Tech Stack:** Python 3.11+, sqlite3, COLMAP CLI, pytest, existing Videoto3D Turntable pipeline.

## Global Constraints

- Do not modify the production `colmap/database.db`.
- Do not modify `colmap/sparse/0`.
- Do not rerun or alter feature extraction.
- Keep `turntable_constrained_essential_v134` fixed.
- Keep `max_gap=10`, `max_step_rotation_deg=20.0`, and `max_model_error_px=3.0` fixed.
- Do not modify Mesh/GLB or Splat/PLY routes.

---

### Task 1: Isolated database copy and matcher contract

**Files:**
- Create: `tools/turntable_matching_ab_v135.py`
- Test: `tests/test_turntable_matching_ab_v135.py`

**Interfaces:**
- Produces: `benchmark_paths(run_root)`, `clone_database_for_exhaustive(source, destination)`, `database_match_stats(database)`, `exhaustive_matcher_args(database)`.

- [x] **Step 1: Write failing tests** that require diagnostic-only paths, feature-preserving database backup, clearing of copied `matches`/`two_view_geometries`, match counters, and guided exhaustive matcher arguments.
- [x] **Step 2: Run the test and verify RED** with `ModuleNotFoundError` because the benchmark module does not yet exist.
- [x] **Step 3: Implement the minimal helpers** using SQLite `backup()` and deletes restricted to the copied database.
- [x] **Step 4: Run the focused tests and verify GREEN.**

### Task 2: Fixed-pose A/B sparse evaluation

**Files:**
- Modify: `tools/turntable_matching_ab_v135.py`
- Test: `tests/test_turntable_matching_ab_v135.py`

**Interfaces:**
- Consumes: existing `read_turntable_constrained_constraints`, `solve_free_span_increments`, known-pose helpers, and `point_triangulator` helpers.
- Produces: `run_matching_ab_benchmark(project_root, run_id, colmap_path=None, overwrite=True)` and `matching_ab_report.json`.

- [x] **Step 1: Add comparison tests** for verified-pair, coverage, point-count, track-length, and reprojection deltas.
- [x] **Step 2: Implement Sequential evaluation** against the existing source database without writing to it.
- [x] **Step 3: Implement Exhaustive evaluation** against the copied/rematched database.
- [x] **Step 4: Record identical pose settings for both branches** and emit source-database before/after SHA256 values.
- [x] **Step 5: Keep all known models, triangulated candidates, logs, and report data below `colmap/diagnostics/matching_ab_v135/`.**

### Task 3: Verification and delivery

**Files:**
- Create: `docs/superpowers/specs/2026-08-18-v135-turntable-matching-ab-design.md`
- Create: `docs/superpowers/plans/2026-08-18-v135-turntable-matching-ab-plan.md`

- [ ] **Step 1: Run focused pytest** for the V1.3.5 benchmark.
- [ ] **Step 2: Run `py_compile`** on the new tool and test.
- [ ] **Step 3: Run `--help`** to verify CLI parsing without needing COLMAP execution.
- [ ] **Step 4: Check LF line endings and trailing whitespace.**
- [ ] **Step 5: Build an incremental ZIP containing only the tool, test, spec, and plan.**
- [ ] **Step 6: Verify ZIP integrity and SHA256.**
