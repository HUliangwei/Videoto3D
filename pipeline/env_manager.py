"""Project-local Conda environment management for Videoto3D.

This module intentionally uses only the Python standard library so it can be
used by the outer bootstrap interpreter before the project core environment
exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ENVIRONMENT_NAMES = ("core", "seg", "gui")
MARKER_NAME = ".videoto3d-env.json"
STATE_SCHEMA = 1

CORE_RUNTIME_PROBE = (
    "import cv2,numpy; from PIL import Image; "
    "assert hasattr(cv2, 'SIFT_create'), 'OpenCV SIFT unavailable'; "
    "print('OpenCV', cv2.__version__, 'SIFT=READY', numpy.__version__, Image.__version__)"
)

SEG_TORCH_PACKAGES = (
    "torch==2.5.1",
    "torchvision==0.20.1",
)
SEG_TORCH_INDEX = "https://download.pytorch.org/whl/cu121"
SEG_EXTRA_PACKAGES = (
    "opencv-python>=4.10,<5.1",
    "packaging>=24,<27",
)


class EnvironmentSetupError(RuntimeError):
    pass


class CondaPrerequisiteError(EnvironmentSetupError):
    """Raised when the external A1 Conda prerequisite cannot be located."""


def conda_prerequisite_message():
    return (
        "Conda not found. Videoto3D A1 requires Anaconda or Miniconda to be installed once.\n"
        "Check: conda --version\n"
        "After installing Conda, reopen PowerShell/Anaconda Prompt and rerun: python Videoto3D.py gui"
    )


def _validate_name(name):
    name = str(name).lower()
    if name not in ENVIRONMENT_NAMES:
        raise ValueError("Unknown Videoto3D environment: {}".format(name))
    return name


def environment_prefix(root, name):
    return Path(root) / "env" / _validate_name(name)


def environment_python(root, name):
    # Videoto3D is currently a Windows-native workflow.
    return environment_prefix(root, name) / "python.exe"


def recipe_path(root, name):
    return Path(root) / "config" / "envs" / ("{}.yml".format(_validate_name(name)))


def marker_path(root, name):
    return environment_prefix(root, name) / MARKER_NAME


def _hash_file(hasher, path):
    path = Path(path)
    if not path.exists() or not path.is_file():
        return
    hasher.update(str(path.name).encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(path.read_bytes())
    hasher.update(b"\0")


def recipe_hash(root, name):
    root = Path(root)
    name = _validate_name(name)
    hasher = hashlib.sha256()
    _hash_file(hasher, recipe_path(root, name))

    if name == "gui":
        _hash_file(hasher, root / "gui" / "control" / "server" / "requirements.txt")
    elif name == "seg":
        hasher.update("\n".join(SEG_TORCH_PACKAGES).encode("utf-8"))
        hasher.update(SEG_TORCH_INDEX.encode("utf-8"))
        hasher.update("\n".join(SEG_EXTRA_PACKAGES).encode("utf-8"))
        _hash_file(hasher, root / "runtime" / "sam2" / "repo" / "setup.py")
        _hash_file(hasher, root / "runtime" / "sam2" / "repo" / "pyproject.toml")

    return hasher.hexdigest()


def _common_conda_candidates():
    user = Path.home()
    return [
        Path(r"C:\ProgramData\Anaconda3\Scripts\conda.exe"),
        Path(r"C:\ProgramData\Miniconda3\Scripts\conda.exe"),
        user / "anaconda3" / "Scripts" / "conda.exe",
        user / "miniconda3" / "Scripts" / "conda.exe",
        user / "AppData" / "Local" / "anaconda3" / "Scripts" / "conda.exe",
        user / "AppData" / "Local" / "miniconda3" / "Scripts" / "conda.exe",
    ]


def find_conda():
    env_value = os.environ.get("CONDA_EXE")
    if env_value:
        candidate = Path(env_value)
        if candidate.exists():
            return candidate

    on_path = shutil.which("conda") or shutil.which("conda.exe")
    if on_path:
        return Path(on_path)

    for candidate in _common_conda_candidates():
        if candidate.exists():
            return candidate

    raise CondaPrerequisiteError(conda_prerequisite_message())


def _load_marker(root, name):
    path = marker_path(root, name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def environment_status(root, name):
    name = _validate_name(name)
    python_path = environment_python(root, name)
    prefix = environment_prefix(root, name)
    marker = _load_marker(root, name)
    expected_hash = recipe_hash(root, name)

    if not prefix.exists():
        status = "MISSING"
    elif not python_path.exists():
        status = "BROKEN"
    elif not marker or not marker.get("ready"):
        status = "STALE"
    elif marker.get("recipe_hash") != expected_hash:
        status = "STALE"
    else:
        status = "READY"

    return {
        "environment": name,
        "status": status,
        "prefix": str(prefix),
        "python": str(python_path),
        "recipe_hash": expected_hash,
    }


def _run_checked(runner, command, root, env=None):
    result = runner(
        [str(item) for item in command],
        cwd=str(root),
        env=env,
    )
    code = getattr(result, "returncode", 0)
    if code != 0:
        raise EnvironmentSetupError(
            "Environment command failed (exit {}): {}".format(
                code,
                " ".join(str(item) for item in command),
            )
        )
    return result


def _post_install(root, name, python_path, runner):
    root = Path(root)
    if name == "gui":
        requirements = root / "gui" / "control" / "server" / "requirements.txt"
        _run_checked(
            runner,
            [python_path, "-m", "pip", "install", "-r", requirements],
            root,
        )
    elif name == "seg":
        sam2_repo = root / "runtime" / "sam2" / "repo"
        if not sam2_repo.exists():
            raise EnvironmentSetupError(
                "SAM2 repo is missing: {}. Restore runtime/sam2/repo before creating env/seg.".format(
                    sam2_repo
                )
            )
        _run_checked(
            runner,
            [python_path, "-m", "pip", "install", *SEG_TORCH_PACKAGES, "--index-url", SEG_TORCH_INDEX],
            root,
        )
        _run_checked(
            runner,
            [python_path, "-m", "pip", "install", *SEG_EXTRA_PACKAGES],
            root,
        )
        install_env = os.environ.copy()
        install_env["SAM2_BUILD_CUDA"] = "0"
        _run_checked(
            runner,
            [python_path, "-m", "pip", "install", "--no-build-isolation", "-e", str(sam2_repo)],
            root,
            env=install_env,
        )


def core_runtime_status(root, runner=subprocess.run):
    """Probe installed core CV runtime without changing the environment."""
    root = Path(root)
    python_path = environment_python(root, "core")
    if not python_path.exists():
        return {
            "ready": False,
            "detail": "core Python missing: {}".format(python_path),
        }
    result = runner(
        [str(python_path), "-c", CORE_RUNTIME_PROBE],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    detail = (getattr(result, "stdout", "") or "").strip()
    return {
        "ready": int(getattr(result, "returncode", 1)) == 0,
        "detail": detail or "core runtime probe returned no output",
    }

def _validate_environment(root, name, python_path, runner):
    probes = {
        "core": CORE_RUNTIME_PROBE,
        "gui": "import fastapi,uvicorn; print(fastapi.__version__,uvicorn.__version__)",
        "seg": (
            "import cv2,torch,sam2; "
            "assert torch.cuda.is_available(), 'CUDA unavailable'; "
            "print(torch.__version__, torch.cuda.get_device_name(0))"
        ),
    }
    _run_checked(runner, [python_path, "-c", probes[name]], root)


def _write_marker(root, name):
    prefix = environment_prefix(root, name)
    prefix.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": STATE_SCHEMA,
        "environment": name,
        "recipe_hash": recipe_hash(root, name),
        "python": str(environment_python(root, name)),
        "ready": True,
    }
    marker_path(root, name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ensure_environment(root, name, conda_path=None, runner=subprocess.run):
    root = Path(root)
    name = _validate_name(name)
    recipe = recipe_path(root, name)
    if not recipe.exists():
        raise EnvironmentSetupError("Environment recipe missing: {}".format(recipe))

    status = environment_status(root, name)
    if status["status"] == "READY":
        return environment_python(root, name)

    conda = Path(conda_path) if conda_path else find_conda()
    prefix = environment_prefix(root, name)
    python_path = environment_python(root, name)

    print("[ENV][{}] {}".format(status["status"], name))
    if prefix.exists() and python_path.exists():
        print("[ENV][UPDATE] {} -> {}".format(name, prefix))
        command = [conda, "env", "update", "-p", prefix, "-f", recipe, "--prune"]
    else:
        if prefix.exists():
            shutil.rmtree(prefix, ignore_errors=True)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        print("[ENV][CREATE] {} -> {}".format(name, prefix))
        command = [conda, "env", "create", "-p", prefix, "-f", recipe]

    _run_checked(runner, command, root)
    if not python_path.exists():
        raise EnvironmentSetupError(
            "Conda finished but environment Python was not created: {}".format(python_path)
        )

    _post_install(root, name, python_path, runner)
    _validate_environment(root, name, python_path, runner)
    _write_marker(root, name)
    print("[ENV][READY] {}".format(name))
    return python_path


def repair_environment(root, name, conda_path=None, runner=subprocess.run):
    root = Path(root)
    name = _validate_name(name)
    prefix = environment_prefix(root, name)
    if prefix.exists():
        print("[ENV][REPAIR] removing {}".format(prefix))
        shutil.rmtree(prefix)
    return ensure_environment(root, name, conda_path=conda_path, runner=runner)
