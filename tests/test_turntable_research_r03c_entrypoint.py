import subprocess
import sys
from pathlib import Path


def test_r03c_tool_supports_direct_entrypoint():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "turntable_r03c_hypothesis_benchmark.py"), "--help"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert result.returncode == 0, result.stdout
    assert "hypothesis" in result.stdout.lower()
    assert "--r03b-report" in result.stdout
