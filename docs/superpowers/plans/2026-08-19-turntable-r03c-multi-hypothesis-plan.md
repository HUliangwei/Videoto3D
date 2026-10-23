# Turntable R0.3c Implementation Plan

- [ ] RED: exact synthetic pair must contain the true angle in top-K.
- [ ] RED: candidate generation API must not accept anchor trajectory angles.
- [ ] GREEN: broad structured angle scan + local minima + fine refinement.
- [ ] RED/GREEN: hypotheses sorted by residual and separated.
- [ ] RED/GREEN: direct benchmark entrypoint supports `--help`.
- [ ] Benchmark tool reuses R0.3b axis/u with `--r03b-report` for fast execution.
- [ ] GT is loaded only after all hypotheses have been generated.
- [ ] Preserve R0.3b and BUG-0014 files.
- [ ] Package updater, syntax verification, targeted regression, ZIP CRC and SHA256.
