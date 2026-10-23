# Turntable R0.3b Robust Multi-Baseline Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:test-driven-development and
> superpowers:verification-before-completion.

**Goal:** Add diagnostic gating and robust fixed weighting for long-baseline
Turntable edges without changing the validated R0.3a solver baseline.

**Architecture:** Use the reliable GT-free gap {1,2,3} result as an anchor for
edge diagnostics. Keep R0.3a frozen; implement weighted robust objective and
trajectory/geometry alternating optimization in a new module. Run strict
weighting/gating A/B configurations from the same anchor state.

**Tech Stack:** Python, NumPy, OpenCV, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-turntable-r03b-robust-graph-design.md`

## Global constraints

- GT pose/span are evaluation-only.
- No forced 360-degree span.
- Fixed edge weights during optimization.
- Gap <= 3 edges are retained by default.
- Do not modify R0.2a, R0.2b-1, R0.2b-2.1 or R0.3a math modules.
- Preserve BUG-0014.

### Task 1: Fixed weighting strategies
- [ ] RED tests for equal-edge, equal-family, sqrt-family and confidence weights.
- [ ] Implement `robust_graph_weights`.
- [ ] GREEN tests.

### Task 2: Edge diagnostics and adaptive gating
- [ ] RED test with a synthetic bad long-baseline edge.
- [ ] Implement per-edge local angle search and diagnostics.
- [ ] Implement trusted-edge robust thresholds and long-edge rejection.
- [ ] GREEN tests.

### Task 3: Weighted robust graph objective
- [ ] RED test proving fixed custom weights change objective contribution.
- [ ] Implement weighted graph objective with optional robust regularity.
- [ ] GREEN tests.

### Task 4: Stable robust solver
- [ ] RED test for monotonic fixed-weight accepted history.
- [ ] Implement weighted coordinate descent and alternating geometry update.
- [ ] Preserve best-state/termination semantics.
- [ ] GREEN tests.

### Task 5: Strict R0.3b benchmark
- [ ] RED `--help` entrypoint test.
- [ ] Implement one cached observation union.
- [ ] Produce A adjacent and B gap123 anchor.
- [ ] Diagnose/gate gap5 edges from B without GT.
- [ ] Run equal-family/equal-edge/sqrt-family/gated-confidence variants from B.
- [ ] Load GT only after predictions exist and report promotion.
- [ ] GREEN test.

### Task 6: Regression and package
- [ ] Run R0.3b tests in isolated fixture.
- [ ] Run R0.3a and BUG-0014 preservation tests.
- [ ] Verify lower-level math hashes unchanged.
- [ ] Build updater and cumulative ZIP.
- [ ] Verify ZIP CRC, Python syntax and SHA256.
