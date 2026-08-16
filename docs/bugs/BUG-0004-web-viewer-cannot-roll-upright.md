# BUG-0004 — Web Viewer cannot roll an arbitrarily oriented asset upright

## Status
Resolved in V1.0.2.

## Symptom
The Teddy GLB could be displayed upside down in the Web Viewer. Left-drag orbiting could not roll the view into the desired upright orientation, and fixed axis presets restored the same world-up assumption.

## Root cause
V1.0.1 used Three.js `OrbitControls` and explicitly reset `camera.up` to world Y in the preset-view path. OrbitControls intentionally maintains a constant camera up direction, so it is not suitable when inspection requires unrestricted roll around the viewing axis. The asset itself may have a valid transform while still being inconvenient relative to the viewer's assumed world-up.

## Resolution
V1.0.2 uses `TrackballControls`, whose official Three.js implementation does not maintain a constant camera `up` vector. It also adds explicit `Roll Left`, `Flip`, and `Roll Right` actions. Axis presets preserve the current roll where possible instead of forcing world-Y up on every view change.

## Regression guard
`tests/test_gui_frontend_contract.py` requires TrackballControls, rejects OrbitControls in the reusable Viewer, and requires the three roll controls.
