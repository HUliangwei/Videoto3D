import subprocess
import sys
from pathlib import Path


def _run_help(script):
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, str(root / "tools" / script), "--help"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_r04_global_orbit_entrypoint():
    result = _run_help("turntable_r04_global_orbit.py")
    assert result.returncode == 0, result.stdout
    assert "global orbit" in result.stdout.lower()
    assert "--r03c-report" in result.stdout


def test_r05_fast_glb_entrypoint():
    result = _run_help("turntable_r05_known_pose_glb.py")
    assert result.returncode == 0, result.stdout
    assert "glb" in result.stdout.lower()
    assert "--orbit-report" in result.stdout
    assert "--openmvs-bin" in result.stdout
