# V1.3.5 Turntable Matching A/B Design

## Goal

Determine whether COLMAP Exhaustive Matching improves Turntable sparse geometry over the current Sequential Matching baseline while holding the V1.3.4 constrained pose estimator, extracted SIFT features, SAM2 masks, angle-graph limits, and known-pose triangulation constant.

## Scope

This is a diagnostic benchmark only. It must not modify the production `workspace/runs/<run>/colmap/database.db` or `colmap/sparse/0`. It must not change feature extraction, SAM2, the V1.3.4 constrained angle estimator, OpenMVS, Blender, Brush, GLB, PLY, Viewer, or Studio.

For a run such as `hlw_04`, the existing `database.db` is the Sequential baseline. The tool creates an SQLite backup below `colmap/diagnostics/matching_ab_v135/exhaustive/database.db`, clears only the copied `matches` and `two_view_geometries` tables, and runs `COLMAP exhaustive_matcher` with guided matching and GPU matching enabled. Existing keypoints, descriptors, cameras, and image identifiers are preserved.

## Controlled A/B

Both branches use the same:

- frame images and SAM2 masks;
- existing mask-guided SIFT keypoints/descriptors;
- `turntable_constrained_essential_v134` pose estimator;
- `min_inliers=12`;
- `max_gap=10`;
- `max_step_rotation_deg=20.0`;
- `max_model_error_px=3.0`;
- CW/CCW known-pose generation and candidate selection;
- COLMAP `point_triangulator`.

The only changed variable is the matcher: current Sequential baseline versus Exhaustive Matching.

## Outputs

All files live under:

`workspace/runs/<run>/colmap/diagnostics/matching_ab_v135/`

The JSON report records raw and verified match counts, accepted constrained pose edges, adjacent and graph coverage, angle span and residuals, CW/CCW sparse statistics, selected sparse points, mean track length, and mean reprojection error. It also hashes the source database before and after the benchmark to verify that the production database was not modified.

## Decision Rule

Do not choose Exhaustive Matching solely because it creates more sparse points. The most important evidence is whether graph/adjacent coverage and mean track length improve together without material reprojection-error degradation. If Exhaustive improves those measures, it becomes the candidate Turntable production matcher. If track length remains near the Sequential baseline, the next isolated experiment is stronger feature extraction (affine shape / DSP-SIFT), not another pose-algorithm change.
