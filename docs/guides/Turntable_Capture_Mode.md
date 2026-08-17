# Videoto3D Turntable Capture Mode

## 1. When to use it

Choose **Turntable** when:

```text
Camera: fixed
Subject: rotates as one rigid object
Background: fixed
```

Typical subjects:

- figurines and toys
- ceramics
- product prototypes
- electronic enclosures / PCB assemblies
- small robot parts
- a person holding an essentially unchanged pose

Do not use it for walking, waving, changing facial expressions, independently moving limbs, or large cloth/hair deformation. Those are dynamic-scene problems.

## 2. Why the normal Orbit workflow is different

Orbit Camera capture:

```text
object fixed + camera moves
```

Static background features agree with camera motion and can improve pose estimation, so Videoto3D uses full-RGB COLMAP SfM.

Turntable capture:

```text
camera fixed + object rotates
```

The background says “camera did not move,” while the object says “viewpoint changed.” V1.3 resolves this by allowing COLMAP to extract features only inside the SAM2 subject masks.

## 3. Mathematical equivalence for a rigid subject

Let a point in object coordinates be `X_o`. At frame `t`, the physical object transform is:

```text
X_c(t) = R_o(t) X_o + t_o(t)
```

If we instead choose the object as the fixed world coordinate system, the same relative geometry can be described by the inverse transform:

```text
T_equivalent_camera(t) = T_object(t)^-1
```

Therefore a rigid rotating object can be reconstructed as if a virtual camera moved around a static object.

The crucial condition is that feature correspondences must come from the rotating rigid subject rather than the static background.

## 4. V1.3 data flow

```text
Video
↓
FFmpeg Frames
↓
SAM2 Subject Masks
↓
COLMAP Feature Extraction
  ImageReader.mask_path = masks/
↓
Sequential Matching
↓
Mapper / Bundle Adjustment
↓
Equivalent Camera Trajectory + Sparse Points
↓
Mesh Route / Splat Route
```

Mask naming already matches COLMAP's expected image-relative convention:

```text
frames/frame_0001.jpg
masks/frame_0001.jpg.png
```

## 5. GUI

New Run → Capture Mode:

```text
Orbit Camera
  Object stationary; move the camera around it.

Turntable
  Camera stationary; rotate a rigid subject.
```

The selected value is written into `run.json` and displayed on the Run detail page.

## 6. CLI

Create a Turntable Run:

```powershell
python app.py run extract --run doll_turntable --input .\input.mp4 --capture-mode turntable
python app.py run mask --run doll_turntable
python app.py run sparse --run doll_turntable
```

Or one-route execution:

```powershell
python app.py route splat --run doll_turntable --input .\input.mp4 --capture-mode turntable
```

For an existing Run, capture mode is persistent. To change capture mode safely, rerun with an input video so Shared data is rebuilt instead of silently reinterpreting an existing reconstruction.

## 7. Capture recommendations

- Keep the camera, focal length and zoom fixed.
- Lock exposure/white balance when possible.
- Keep the complete subject inside frame.
- Prefer diffuse lighting; avoid a highlight that rotates independently across glossy surfaces.
- Rotate smoothly through roughly 360°.
- Ensure adjacent extracted frames still share enough textured surface.
- A textured rigid turntable is easier than a glossy, transparent, featureless object.

## 8. What to inspect first

In Pipeline Artifacts:

```text
Frames
→ SAM2 Masks
→ COLMAP Sparse
→ Camera Trajectory
```

If masks are wrong, fix them before judging SfM. If Camera Trajectory collapses, the object may have too few features, the masks may be too tight/unstable, or the rotation sampling may be unsuitable.

The browser trajectory is intentionally a compact camera-center point cloud; full COLMAP camera frustums remain available in the COLMAP Viewer.
