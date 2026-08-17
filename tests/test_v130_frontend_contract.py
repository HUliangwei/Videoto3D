from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_new_run_exposes_capture_mode_and_api_forwards_it():
    panel = read("gui/control/web/src/components/NewRunPanel.tsx")
    api = read("gui/control/web/src/api.ts")
    types = read("gui/control/web/src/types.ts")
    assert "Orbit Camera" in panel
    assert "Turntable" in panel
    assert "captureMode" in panel
    assert "capture_mode" in api
    assert "CaptureMode" in types


def test_backend_records_and_exposes_capture_mode():
    server = read("gui/control/server/app.py")
    service = read("gui/control/server/service.py")
    core = read("app.py")
    assert "--capture-mode" in server
    assert '"capture_mode"' in service
    assert "sparse_mask_path" in core
    assert "mask_guided" in core


def test_readme_documents_both_capture_modes_and_dynamic_human_limit():
    readme = read("README.md")
    assert "Orbit Camera" in readme
    assert "Turntable" in readme
    assert "mask-guided" in readme.lower()
    assert "Dynamic / 4D" in readme
