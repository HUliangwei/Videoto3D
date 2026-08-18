"""Canonical Videoto3D V1.4 command entry point.

Examples:
    python Videoto3D.py gui
    python Videoto3D.py run sparse --run <run_id>
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__" and os.name == "nt":
    from bootstrap import bootstrap_entry
    bootstrap_result = bootstrap_entry(ROOT, sys.argv[1:])
    if bootstrap_result is not None:
        sys.exit(bootstrap_result)

from app import main

if __name__ == "__main__":
    sys.exit(main())
