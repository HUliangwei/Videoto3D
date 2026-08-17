# ADR-0010 · Turntable Capture uses SAM2 mask-guided SfM

Status: Accepted  
Version: Videoto3D V1.3.0

## Context

Videoto3D V1.2 assumes a mostly static scene: the object is stationary while the camera moves. In that capture geometry, background texture is useful to COLMAP, so Shared SfM deliberately uses the original RGB frames.

A turntable capture reverses the physical motion: the camera stays fixed while a rigid subject rotates. Static background features then vote for an unchanged camera and conflict with the moving subject. Feeding all RGB features to SfM can therefore create a degenerate or background-dominated reconstruction.

For a rigid object, only the relative transform matters. If the object transform is `T_object(t)`, the same image formation can be represented in an object-fixed coordinate system with an equivalent camera transform proportional to `T_object(t)^-1`.

## Decision

Introduce top-level Run field:

```json
{"capture_mode": "orbit_camera"}
```

Allowed values:

```text
orbit_camera
turntable
```

### Orbit Camera

```text
Original RGB Frames
→ COLMAP feature extraction over the full image
→ Shared Sparse / Camera Poses
```

This is the V1.2 behavior and remains the default for backwards compatibility.

### Turntable

```text
Original RGB Frames
→ SAM2 masks
→ COLMAP ImageReader.mask_path
→ features only inside the subject mask
→ Shared Sparse / Equivalent Camera Poses
```

The RGB pixels are not replaced by a synthetic black-background image. The mask only controls where COLMAP is allowed to extract features.

Changing a Turntable Run's SAM2 masks invalidates Shared Sparse because those masks participate directly in SfM. In Orbit Camera mode, changing masks does not invalidate Shared Sparse.

## Artifact / QA consequence

Artifact Inspector adds **Camera Trajectory**, visualized as registered camera-center points. For Turntable mode, a healthy reconstruction should usually show meaningful viewpoint movement around the reconstructed object instead of all centers collapsing to one location.

## Scope boundary

Turntable mode assumes a rigid subject. A person can only be treated this way when pose, expression, clothing and hair remain approximately static while the whole body rotates. Articulated motion belongs to Dynamic / 4D reconstruction and is intentionally out of scope for V1.3.
