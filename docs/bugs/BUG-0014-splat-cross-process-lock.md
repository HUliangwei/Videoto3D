# BUG-0014: Splat canonical PLY can be locked on Windows

Observed symptom:

`PermissionError: [WinError 32] ... chair_raw.ply`

Root cause:
- GUI JobManager conflict prevention is process-local and cannot
  coordinate a separate CLI process.
- Brush Viewer previously opened the mutable canonical PLY directly.

Retained fix in the R0.2b-1 follow-up package:
- OS-backed non-blocking `splat` Run lock around the complete
  training + cleanup route.
- Brush Viewer opens immutable copies under `splat/viewer_cache/`.

The follow-up overlay deliberately carries `pipeline/run_lock.py`,
`pipeline/viewer_snapshot.py`, and the regression tests forward.
