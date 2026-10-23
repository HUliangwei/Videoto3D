import subprocess
import sys
from pathlib import Path


def test_r03b_robust_tool_supports_direct_entrypoint():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "turntable_r03b_robust_ab_benchmark.py"),
            "--help",
        ],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert result.returncode == 0, result.stdout
    assert "robust" in result.stdout.lower()
    assert "gap5" in result.stdout.lower()
