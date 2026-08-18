from pathlib import Path


def test_image_viewer_waits_for_real_image_dimensions_before_fit():
    source = Path("gui/control/web/src/components/ArtifactInspector.tsx").read_text(encoding="utf-8")
    assert "image.naturalWidth <= 0" in source
    assert "image.naturalHeight <= 0" in source
    assert "readyRef.current = true" in source
    assert "const frame = requestAnimationFrame(syncLoadedImages)" in source
    assert "visibility: naturalSize ? 'visible' : 'hidden'" in source


def test_image_viewer_fit_is_hard_minimum_and_recenters():
    source = Path("gui/control/web/src/components/ArtifactInspector.tsx").read_text(encoding="utf-8")
    assert "const minScale = fitScale" in source
    assert "applyView(fitScale, 0, 0)" in source
    assert "view.scale <= fitPercent * 1.001" in source


def test_image_viewer_owns_wheel_without_page_scroll():
    source = Path("gui/control/web/src/components/ArtifactInspector.tsx").read_text(encoding="utf-8")
    assert "host.addEventListener('wheel', handler, { passive: false })" in source
    assert "event.preventDefault()" in source
    assert "event.stopPropagation()" in source
    css = Path("gui/control/web/src/components/artifact-inspector.css").read_text(encoding="utf-8")
    assert "overscroll-behavior:contain" in css


def test_3d_viewer_contains_scroll_without_changing_asset_pipeline():
    source = Path("gui/viewer/src/AssetViewer.tsx").read_text(encoding="utf-8")
    assert "renderer.domElement.addEventListener('wheel', isolateWheel, { passive: false })" in source
    assert "overscrollBehavior:'contain'" in source
    assert "new GLTFLoader().load" in source
    assert "new PLYLoader().load" in source
    assert "new SplatMesh" in source


def test_launcher_reuses_same_project_and_falls_forward_on_busy_port():
    source = Path("gui/control/server/launcher.py").read_text(encoding="utf-8")
    assert "def _probe_gui_health" in source
    assert 'url + "/api/health"' in source
    assert "def _select_gui_target" in source
    assert "reuse existing Studio instance" in source
    assert "port {} is busy; using {} instead." in source
    assert '"--strict-port"' in source
    assert 'GUI_VERSION = "1.3.3.2"' in source
