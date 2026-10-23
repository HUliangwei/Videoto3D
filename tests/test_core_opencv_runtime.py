from pathlib import Path
from unittest import mock

from pipeline.env_manager import core_runtime_status


def test_core_recipe_declares_headless_opencv():
    root = Path(__file__).resolve().parents[1]
    recipe = (
        root / "config" / "envs" / "core.yml"
    ).read_text(encoding="utf-8")
    assert (
        "opencv-python-headless==4.13.0.92"
        in recipe
    )


def test_core_runtime_probe_checks_sift(tmp_path):
    python = (
        tmp_path
        / "env"
        / "core"
        / "python.exe"
    )
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append((list(command), kwargs))
        return mock.Mock(
            returncode=0,
            stdout="OpenCV 4.13.0 SIFT=READY\n",
        )

    status = core_runtime_status(
        tmp_path,
        runner=runner,
    )
    assert status["ready"] is True
    assert "SIFT=READY" in status["detail"]
    assert "SIFT_create" in calls[0][0][-1]


def test_doctor_source_reports_core_runtime():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(
        encoding="utf-8"
    )
    assert "core_runtime_status(ROOT)" in source
    assert "Core CV runtime" in source
