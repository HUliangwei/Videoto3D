"""Stdlib-only entry bootstrap for Videoto3D project-local core environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pipeline.env_manager import (
    CondaPrerequisiteError,
    environment_python,
    ensure_environment,
    repair_environment,
)


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def bootstrap_core(root, argv, executable=None, execv=os.execv):
    root = Path(root)
    argv = [str(item) for item in argv]
    executable = Path(executable or sys.executable)
    target = environment_python(root, "core")

    if _same_path(executable, target):
        return False

    if [item.lower() for item in argv[:3]] == ["env", "repair", "core"]:
        repair_environment(root, "core")
        print("[ENV][READY] core repair complete")
        return True

    target = ensure_environment(root, "core")
    os.environ["PYTHONNOUSERSITE"] = "1"
    execv(
        str(target),
        [str(target), str(root / "Videoto3D.py"), *argv],
    )
    return True


def bootstrap_entry(root, argv, stream=None, **kwargs):
    """Run the outer bootstrap and turn missing A1 prerequisites into a concise user-facing result."""
    stream = stream or sys.stdout
    try:
        handled = bootstrap_core(root, argv, **kwargs)
    except CondaPrerequisiteError as exc:
        print("=" * 68, file=stream)
        print("Videoto3D Prerequisite Check", file=stream)
        print("[PREREQ][MISSING] Conda", file=stream)
        print(str(exc), file=stream)
        print("=" * 68, file=stream)
        return 2
    return 0 if handled else None
