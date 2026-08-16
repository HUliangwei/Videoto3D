# ADR-0004: Post-Brush Splat Cleanup + Unified Quality Report

- Status: Accepted
- Version: Videoto3D V0.11
- Date: 2026-08-17

## Context

V0.10 used SAM2 multi-view votes to filter COLMAP `points3D` before Brush training. This substantially reduced scene clutter while preserving the full RGB COLMAP camera solution, but final Brush outputs could still contain halo/background Gaussians because training can densify, clone and move splats after initialization.

The project should not add another segmentation model, another SfM pass, a custom Brush fork, or a large chain of cleanup algorithms merely to isolate the object.

## Decision

Keep Shared stages unchanged (`frames`, `masks`, RGB `colmap`). Preserve object-only sparse initialization as an optional training optimization. Add exactly one result-level isolation step after Brush:

1. Preserve Brush final checkpoint as `splat/raw/<run_id>_raw.ply`.
2. Project each final Gaussian center through registered COLMAP cameras.
3. Reuse the existing SAM2 masks to collect multi-view foreground votes.
4. Keep a Gaussian when `foreground_support >= 0.70` and `valid_views >= 3` by default.
5. Write the cleaned asset to `output/<run_id>_splat.ply` without modifying the raw PLY.

The cleanup filters complete PLY vertex records, preserving every Gaussian property (SH coefficients, opacity, scale, rotation, etc.) for kept splats.

## Resume semantics

Brush training and Cleanup have independent recipes. Changing only cleanup thresholds must not retrain Brush. A V0.10 final Splat is migrated non-destructively into `splat/raw/`, after which only Cleanup is required.

## Quality report

Each Run can generate `quality/report.json` and `quality/report.md`. The report summarizes Shared registration/segmentation metrics and final Mesh/Splat asset metrics. JSON is the stable input for a future Web GUI; Markdown is the human audit view.

## Consequences

- Both routes continue to share the expensive recognition/SfM work.
- Splat object isolation can be tuned in seconds/minutes without a 30k retrain.
- Cleanup does not perform explicit depth occlusion reasoning; multi-view silhouette consensus is the intentionally minimal V0.11 method. If close halo remains, evaluate evidence before adding more stages.
