# Turntable Free-Span · V1.3.3

## Capture contract

The minimum practical requirements are:

```text
Camera   fixed
Subject  rigid
Axis     one dominant rotation axis
Motion   primarily one direction
Speed    arbitrary
Span     arbitrary
```

You do **not** need to rotate at constant speed and the clip does **not** need to be exactly 360°.

For a complete object, a near-full turn is still recommended because surfaces that never face the camera cannot be reconstructed from the video.

## Geometry path

```text
SAM2 object masks
→ COLMAP mask-guided features
→ sequential verified pair geometry
→ multi-pair 1-D angle graph
→ free-span monotonic theta_i
→ existing CW / CCW known-pose candidates
→ existing COLMAP point_triangulator
→ existing Mesh / GLB route
→ existing Splat / PLY route
```

## Angle report

`workspace/runs/<run_id>/colmap/turntable_angle_report.json` now includes:

- `strategy = adaptive_free_span_graph`
- `total_span_deg`
- `forced_full_turn = false`
- `graph_constraints`
- `graph_gap_coverage_ratio`
- graph residual diagnostics
- estimated per-frame increments and cumulative angles

A low graph coverage ratio means the object did not provide enough reliable geometry. In that case, improve lighting/texture, rotate more slowly, or increase usable frame overlap before tuning Mesh/Splat parameters.
