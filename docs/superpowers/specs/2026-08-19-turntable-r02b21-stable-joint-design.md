# Turntable R0.2b-2.1 Stable Joint Objective Design

## Root cause

The 15-iteration `chair_nonuniform_280` run showed that R0.2b-2 could pass
through better trajectory states and then drift away while some local residual
statistics still improved.

The optimizer used incompatible objectives:
- angle fitting minimized a per-pair median Sampson residual;
- shared geometry fitting minimized trimmed-RMS Sampson error on selected pairs;
- the outer loop had no full-sequence candidate acceptance or best-state return.

## Unified objective

R0.2b-2.1 defines one full-sequence objective over all adjacent pairs:

`J(a,u,theta) = median_focal * sqrt(mean(pair_trimmed_mean_sampson_sq))`

Each positive angle search minimizes the same per-pair term used by `J`.
Every angle or geometry proposal is then scored against the same full-sequence
`J` before it is accepted.

Accepted objective history must be non-increasing.

## Best-state and termination

The solver retains the best accepted `(a, u, delta[])` state and always returns
that state instead of the last attempted state.

Termination reasons are explicit:
- `stable_state`
- `objective_patience`
- `max_iterations`

## Free-span contract

No GT axis, GT orbit, GT angles, GT span, or forced 360-degree prior is added.
Adjacent deltas stay positive because this stage models one-direction capture.

## Initialization bug

A generic Essential hypothesis with `recoverPose()` returning `inliers <= 0`
is rejected at source. It cannot count as a valid initialization pair or inject
an unsupported local delta.

## Preserved boundaries

This patch does not modify:
- R0.2a `structured_fit.py`
- R0.2b-1 `shared_geometry.py`
- Orbit Camera
- frozen `legacy_v13`
- OpenMVS / GLB / PLY production routes

BUG-0014 Splat lock and immutable Viewer snapshot remain carried forward.
