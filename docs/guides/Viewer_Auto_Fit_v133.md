# Viewer Auto Fit · V1.3.3

Artifact previews use a fit-first interaction model.

## Image / Mask previews

- Default: fit the whole image into the preview area.
- Wheel: zoom around the pointer position.
- Left drag while zoomed: pan.
- `Fit` or double click: return to fit view.
- `+` / `-`: centered zoom.
- Changing frame or Original/Mask/Overlay mode resets to Fit.

## 3D previews

The existing Three.js viewer keeps rotate/pan/wheel controls. Fit distance now uses the limiting horizontal/vertical field of view, so narrow containers also fit the complete model. While the view is still in Auto Fit mode, container resize recomputes fit. Any manual camera interaction leaves Auto Fit mode until `Fit`/`Reset` is pressed.
