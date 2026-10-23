# Turntable R0.3c Multi-Hypothesis Pair Estimation

## Purpose
R0.3c is the fast bridge between R0.3b robust graph diagnostics and R0.4 cycle-consistent global orbit.

The pair search is independent of the current global angle trajectory. It uses the GT-free shared axis/transverse geometry from `B_gap123_anchor`, but it does not center the angle search on the anchor trajectory.

## Fast execution
Reuse the existing R0.3b report so shared geometry does not need to be optimized again. Match only gaps 2, 3 and sparse 5, then perform broad structured angle search.

## Primary output
`r03c_hypothesis_report.json`

Key evaluation fields:
- top-1 angle MAE
- top-K oracle MAE
- top-K recall within 0.25 / 0.5 / 1.0 degrees
- per-gap metrics
- per-edge candidate angles/residual/confidence

R0.3c does not perform global cycle selection. That is intentionally reserved for R0.4.
