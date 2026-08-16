# V1.1.2 Route Settings & Path Inspector Design

## Goal
Freeze the V1.x local Studio foundation by making Mesh Route settings inspectable/tunable, exposing read-only project/runtime/run paths, and making the project-local core environment complete for mask validation.

## Scope
- Keep Shared/SAM2/COLMAP architecture unchanged.
- Keep Splat settings behavior unchanged.
- Add a small safe Mesh settings profile: COLMAP undistort max image size, OpenMVS dense resolution level, dense number views, dense max threads, and refine resolution level.
- Keep OpenMVS 2.4.0 seam-leveling workaround locked OFF and visible, not editable.
- Make Mesh reruns recipe-aware: only invalidate the earliest affected Mesh stage and downstream outputs.
- Add a read-only Paths & Runtime inspector with Copy Path controls. No path editing in this release.
- Add Pillow to `env/core` recipe and core health validation.
- Preserve `gui/viewer` portability; all path/settings UI lives in `gui/control`.

## Mesh profile defaults
- undistort_max_image_size: 2000
- dense_resolution_level: 0
- dense_number_views: 0 (`0` means OpenMVS default/auto; omit CLI flag)
- dense_max_threads: 0 (`0` means OpenMVS default/auto; omit CLI flag)
- refine_resolution_level: 1

## Recipe invalidation
- undistort max image size changed: delete cached undistorted COLMAP workspace and invalidate InterfaceCOLMAP + all downstream OpenMVS outputs.
- any dense setting changed: invalidate Dense + Reconstruct + Refine + Texture + GLB.
- refine resolution changed: invalidate Refine + Texture + GLB.
- same recipe: reuse existing cache.
- legacy Mesh output with no recipe file is treated as the default profile so existing successful runs are not unnecessarily rebuilt.

## Paths & Runtime inspector
Read-only groups:
- Project: root, workspace, runtime.
- Environments: core, seg, gui Python paths.
- Tools: saved/detected FFmpeg, COLMAP, OpenMVS, Brush, Blender paths where known.
- Current Run: run root, frames, masks, COLMAP, mesh, splat, GLB, PLY.

## Error handling
- Mesh numeric settings are validated in CLI and API before starting jobs.
- `0` is accepted only for `dense_number_views` and `dense_max_threads` to mean Auto.
- Negative values are rejected.
- Path inspector never writes config.
- Texture seam-leveling flags remain hard-coded OFF under BUG-0001.

## Verification
- Unit tests for OpenMVS argument builders and recipe invalidation.
- CLI parser tests for Mesh settings.
- GUI API tests for route mesh payload and path inspector.
- Frontend contract tests for Mesh Settings and Paths & Runtime UI.
- Environment tests verify Pillow is in core recipe/probe.
- Full Python test suite, compileall, TypeScript syntax parse, fresh overlay ZIP verification.
