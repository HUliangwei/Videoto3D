"""Build/cache the local React GUI when its source changes."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


class FrontendSetupError(RuntimeError):
    pass


def _source_files(root):
    root = Path(root)
    gui = root / "gui"
    fixed = [
        gui / "package.json",
        gui / "control" / "web" / "package.json",
        gui / "control" / "web" / "tsconfig.json",
        gui / "control" / "web" / "vite.config.ts",
        gui / "viewer" / "package.json",
    ]
    dynamic = []
    for base in (gui / "control" / "web" / "src", gui / "viewer" / "src"):
        if base.exists():
            dynamic.extend(path for path in base.rglob("*") if path.is_file())
    return sorted([path for path in fixed + dynamic if path.exists()], key=lambda p: str(p))


def frontend_source_hash(root):
    hasher = hashlib.sha256()
    root = Path(root)
    for path in _source_files(root):
        hasher.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _marker_path(root):
    return Path(root) / "gui" / "control" / "web" / "dist" / ".videoto3d-build.json"


def _is_ready(root):
    root = Path(root)
    dist = root / "gui" / "control" / "web" / "dist"
    marker = _marker_path(root)
    if not (dist / "index.html").exists() or not marker.exists():
        return False
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(state.get("ready")) and state.get("source_hash") == frontend_source_hash(root)


def _run(runner, command, cwd):
    result = runner([str(item) for item in command], cwd=str(cwd))
    code = getattr(result, "returncode", 0)
    if code != 0:
        raise FrontendSetupError(
            "Frontend command failed (exit {}): {}".format(code, " ".join(str(x) for x in command))
        )


def ensure_frontend(root, npm_path=None, runner=subprocess.run):
    root = Path(root)
    if _is_ready(root):
        return root / "gui" / "control" / "web" / "dist"

    npm = npm_path or shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise FrontendSetupError(
            "npm not found. Install Node.js/npm, then rerun python app.py gui."
        )

    gui = root / "gui"
    print("[GUI][SETUP] Frontend source changed or build missing")
    print("[GUI][SETUP] npm install")
    _run(runner, [npm, "install"], gui)
    print("[GUI][SETUP] npm run build")
    _run(runner, [npm, "run", "build"], gui)

    dist = root / "gui" / "control" / "web" / "dist"
    if not (dist / "index.html").exists():
        raise FrontendSetupError("GUI build finished but dist/index.html is missing: {}".format(dist))
    marker = _marker_path(root)
    marker.write_text(
        json.dumps({"schema": 1, "ready": True, "source_hash": frontend_source_hash(root)}, indent=2),
        encoding="utf-8",
    )
    print("[GUI][READY] Frontend build")
    return dist
