# V1.3.1 Turntable Uniform-360 Known-Pose Reconstruction Design

## Goal

Keep the existing manual capture selector and make both capture modes feed both existing output routes:

```text
Orbit Camera ──→ Mesh → GLB
             └─→ Splat → PLY

Turntable   ──→ Mesh → GLB
             └─→ Splat → PLY
```

No automatic capture-mode detection is added.

## Capture contract

Orbit Camera is unchanged: the object is static and the camera moves.

Turntable assumes:
- fixed camera;
- rigid subject;
- input trimmed to one approximately complete 360° rotation;
- roughly uniform rotation speed;
- subject roughly centered;
- turntable axis approximately vertical in the image;
- camera approximately level;
- little/no idle footage before/after the full turn.

## Geometry

For `N` ordered frames:

\[
\theta_i = s 2\pi i/N,\qquad s \in \{+1,-1\}
\]

Object rotation under a fixed camera is represented as an equivalent virtual camera orbit. With an approximately vertical turntable axis:

\[
R_i = R_y(\theta_i), \qquad t_i=t_0
\]

The projected turntable center is approximated using the median SAM2 mask bounding-box center. With SIMPLE_RADIAL `[f,cx,cy,k]` and arbitrary monocular depth scale `tz=1`:

\[
t_x=(u_0-c_x)/f,\qquad t_y=(v_0-c_y)/f,\qquad t_z=1
\]

Both rotation directions are triangulated. The candidate with more sparse 3D points wins; reprojection error breaks ties.

## Turntable Shared Sparse flow

```text
Frames + SAM2 Masks
→ mask-guided COLMAP Feature Extraction
→ Sequential Guided Matching
→ read DB camera + image IDs
→ uniform CW known poses
→ COLMAP point_triangulator
→ uniform CCW known poses
→ COLMAP point_triangulator
→ select stronger sparse model
→ colmap/sparse/0
```

COLMAP's documented `point_triangulator` path is used specifically to create 3D points from registered images with known poses.

## Downstream

No Turntable-specific Mesh/Splat implementation is added:

```text
selected colmap/sparse/0
├─ existing OpenMVS → Blender → GLB
└─ existing object-sparse → Brush → Cleanup → PLY
```

Camera Trajectory automatically visualizes the selected sparse model.

## Out of scope

- automatic capture-mode detection;
- arbitrary non-uniform turntable motion;
- dynamic/4D people;
- metric scale;
- turntable-axis optimization;
- OpenMVS/Brush/Blender changes.
