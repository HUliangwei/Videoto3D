import subprocess
import sys
from pathlib import Path


def test_r02_tools_support_direct_script_entrypoint():
    root = Path(__file__).resolve().parents[1]
    scripts = (
        "tools/turntable_r02_pair_benchmark.py",
        "tools/turntable_r02_sequence_benchmark.py",
        "tools/turntable_r02b1_shared_geometry_benchmark.py",
    )
    for relative in scripts:
        result = subprocess.run(
            [
                sys.executable,
                str(root / relative),
                "--help",
            ],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert result.returncode == 0, result.stdout
        assert "usage:" in result.stdout.lower()
