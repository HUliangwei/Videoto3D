# Videoto3D V1.2.0 Artifact Inspector Design

## Goal

Make every completed reconstruction stage observable in the Local Web Studio so the pipeline is useful for learning, debugging, quality review, and README/demo recording—not only for downloading the final GLB/PLY.

## Scope

The Run page gains a read-only **Pipeline Artifacts** section grouped as:

- Shared: Frames, SAM2 Masks, COLMAP Sparse
- Mesh Route: Dense Cloud, Raw Mesh, Refined Mesh, Texture Atlas, Final GLB
- Splat Route: Object Sparse, Raw Splat, Clean Splat

Each artifact becomes available only when the corresponding file(s) actually exist. The UI distinguishes `READY`, `PARTIAL`, `PENDING`, and `MISSING` so a manifest that claims completion but has lost its file is not silently treated as healthy.

## Preview architecture

`gui/control` remains Videoto3D-specific. It discovers run-local files, builds artifact metadata, streams images/files, and converts COLMAP `points3D.bin` to a browser-readable PLY preview on demand.

`gui/viewer` stays project-agnostic. Its public `AssetViewer` adds generic `pointcloud` and `mesh-ply` asset types using Three.js `PLYLoader`; it still knows nothing about Runs, COLMAP, OpenMVS, SAM2, workspace paths, or the control API.

The control UI opens one artifact at a time in a modal. This avoids creating many simultaneous WebGL contexts on the Run page.

## Sequence previews

Frames use an indexed image viewer.

Masks use the same frame index and offer `Original / Mask / Overlay` modes. Overlay is composed in the browser by stacking the RGB frame and corresponding mask, so the GUI environment does not need a second image-processing dependency.

Texture Atlas supports multiple texture images through the same indexed image viewer.

## 3D previews

- COLMAP Sparse / Object Sparse: converted from `points3D.bin` to binary little-endian PLY with per-point RGB.
- OpenMVS Dense: streamed as PLY and rendered as a generic point cloud.
- Raw / Refined Mesh: streamed as PLY and rendered as a generic mesh.
- GLB: existing GLB viewer.
- Raw / Clean Splat: existing Spark Gaussian Splat viewer.

## Metadata

Artifact cards show cheap, deterministic metrics where available:

- sequence item count;
- COLMAP point count;
- PLY vertex/face count parsed from the header;
- file size;
- texture image count.

No expensive reconstruction or conversion is triggered merely by opening the Run page.

## API

New read-only routes:

- `GET /api/runs/{run_id}/artifacts`
- `GET /api/runs/{run_id}/artifacts/frames/{index}`
- `GET /api/runs/{run_id}/artifacts/masks/{index}`
- `GET /api/runs/{run_id}/artifacts/textures/{index}`
- `GET /api/runs/{run_id}/artifacts/file/{key}`

Artifact keys accepted by the file endpoint are fixed by the server and never accept arbitrary paths.

## Error handling

- Invalid indices -> 404.
- Unknown artifact keys -> 404.
- Missing files -> 404.
- Paths are derived from the validated run root and fixed layouts/manifest fields; no caller-supplied filesystem path is accepted.
- The inspector shows `MISSING` when a stage says ready but its expected file is absent.

## README/demo relationship

V1.2.0 does not embed a finished demo video because the media does not exist yet. Instead the patch includes `docs/guides/Videoto3D_Workflow_Video_Recording.md` with the exact capture plan. After recording, README can be updated with the final GIF/video link without changing pipeline behavior.
