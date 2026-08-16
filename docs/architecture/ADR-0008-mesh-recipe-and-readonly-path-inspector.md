# ADR-0008 · Mesh Recipe and Read-only Path Inspector

## Status
Accepted in Videoto3D V1.1.2.

## Context
Splat Route already exposed a small set of recipe parameters, while Mesh Route exposed only a rerun button even though OpenMVS quality/cost depends on several safe parameters. At the same time, a local-first desktop workflow benefits from making resolved environments/tool/run paths visible without coupling the reusable viewer to Videoto3D configuration writes.

## Decision
1. Add a five-field safe Mesh profile: undistort max image size, dense resolution level, dense number views, dense max threads, and refine resolution level.
2. Persist the requested Mesh profile as `mesh/openmvs/mesh_recipe.json` and in the Mesh texture manifest entry.
3. Invalidate only the earliest affected Mesh stage and its downstream outputs. Shared frames/masks/original RGB sparse remain untouched.
4. Keep OpenMVS 2.4.0 seam-leveling workaround locked OFF; the GUI displays but cannot change it.
5. Add a read-only `Paths & Runtime` panel in `gui/control`. It may know project/run/tool configuration; `gui/viewer` remains asset-only and portable.
6. Path editing is explicitly out of scope for this release.

## Consequences
- Mesh tuning no longer requires source edits or full Shared reruns.
- Existing successful pre-V1.1.2 Mesh outputs are interpreted as the historical default profile, avoiding unnecessary rebuilds.
- Tool path visibility improves debugging while configuration mutation remains centralized in Core/Doctor.
- The reusable Viewer stays suitable for migration to other projects.
