from pathlib import Path


def test_turntable_angle_path_is_free_span_and_graph_based():
    source = Path("pipeline/turntable_angle.py").read_text(encoding="utf-8")
    assert "read_pair_rotation_constraints" in source
    assert "solve_free_span_increments" in source
    assert '"adaptive_free_span_graph"' in source
    assert '"forced_full_turn": False' in source
    assert '"total_span_deg"' in source


def test_capture_mode_copy_no_longer_promises_360_degrees():
    source = Path("pipeline/capture_mode.py").read_text(encoding="utf-8")
    assert "Free-span angle graph + robust constraints + SAM2 features" in source
    assert "Adaptive 360° poses + SAM2 features" not in source


def test_existing_turntable_backend_boundary_is_unchanged():
    source = Path("pipeline/turntable.py").read_text(encoding="utf-8")
    assert "estimate_adaptive_turntable_angles" in source
    assert '"point_triangulator"' in source
    assert "build_pose_records(" in source
    assert "turntable_angle_report.json" in source


def test_image_artifact_viewer_has_fit_zoom_and_pan():
    source = Path("gui/control/web/src/components/ArtifactInspector.tsx").read_text(encoding="utf-8")
    assert "function ImageViewport" in source
    assert "Wheel Zoom · Drag Pan · Double Click Fit" in source
    assert "addEventListener('wheel'" in source or 'addEventListener("wheel"' in source
    assert "passive: false" in source
    assert "preventDefault()" in source
    assert "stopPropagation()" in source
    assert "event.stopPropagation()" in source
    assert "document.body.style.overflow = 'hidden'" in source
    assert "naturalWidth" in source
    assert "onPointerMove=" in source
    assert ">Fit</button>" in source


def test_3d_viewer_keeps_existing_controls_and_adds_resize_auto_fit():
    source = Path("gui/viewer/src/AssetViewer.tsx").read_text(encoding="utf-8")
    assert "TrackballControls" in source
    assert "controls.zoomSpeed" in source
    assert "controls.panSpeed" in source
    assert "autoFitMode" in source
    assert "limitingFov" in source
    assert "radius / Math.sin" in source
    assert "isolateWheel" in source
    assert "if (autoFitMode && !objectBox.isEmpty()) fitBox(objectBox)" in source
