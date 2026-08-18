# V1.4 Splat Cross-Process Guard Design

Use an OS-backed Run-level `splat` lock around the full route and viewer
snapshots so Windows viewers never own the canonical mutable PLY.
