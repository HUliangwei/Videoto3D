
import json
import os
import re
import subprocess
from pathlib import Path

from pipeline.env_manager import ensure_environment, environment_python


DEFAULT_CONFIG_NAME = "segmentation.json"


def segmentation_python_path(root):
    return environment_python(root, "seg")


def load_segmentation_config(path):
    path = Path(path)

    if not path.exists():
        return {}

    try:
        raw = path.read_text(
            encoding="utf-8-sig"
        ).strip()
    except OSError:
        return {}

    if not raw:
        return {}

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return value if isinstance(value, dict) else {}


def _is_windows_absolute(value):
    text = str(value)
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", text)
        or text.startswith("\\\\")
    )


def _resolve_path(value, root):
    if not value:
        return None

    if _is_windows_absolute(value):
        return Path(value)

    path = Path(value)

    if path.is_absolute():
        return path

    return Path(root) / path


def resolve_config_paths(config, root):
    root = Path(root)
    resolved = dict(config)

    for key in (
        "python",
        "sam2_repo",
        "checkpoint",
    ):
        if config.get(key):
            resolved[key] = _resolve_path(
                config[key],
                root,
            )

    return resolved


def _sam2_config_file(runtime):
    repo = Path(runtime["sam2_repo"])
    config_name = runtime["model_config"]

    # Hydra config names are e.g.
    # configs/sam2.1/sam2.1_hiera_s.yaml,
    # while the physical file lives under sam2/configs/.
    return repo / "sam2" / config_name


def validate_segmentation_runtime(
    runtime,
    runner=subprocess.run,
):
    required = (
        "python",
        "sam2_repo",
        "checkpoint",
        "model_config",
    )

    missing_keys = [
        key
        for key in required
        if not runtime.get(key)
    ]

    if missing_keys:
        return (
            False,
            "Missing segmentation config keys: "
            + ", ".join(missing_keys),
        )

    python_path = Path(runtime["python"])
    repo = Path(runtime["sam2_repo"])
    checkpoint = Path(runtime["checkpoint"])

    if not python_path.exists():
        return (
            False,
            "Segmentation Python not found: {}".format(
                python_path
            ),
        )

    if not repo.exists():
        return (
            False,
            "SAM2 repo not found: {}".format(repo),
        )

    if not checkpoint.exists():
        return (
            False,
            "SAM2 checkpoint not found: {}".format(
                checkpoint
            ),
        )

    physical_config = _sam2_config_file(runtime)

    if not physical_config.exists():
        return (
            False,
            "SAM2 model config not found: {}".format(
                physical_config
            ),
        )

    probe = (
        "import json,sys,torch,sam2;"
        "print(json.dumps({"
        "'python':[sys.version_info.major,sys.version_info.minor],"
        "'torch':torch.__version__,"
        "'cuda':bool(torch.cuda.is_available()),"
        "'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None"
        "}))"
    )

    env = os.environ.copy()
    repo_text = str(repo)
    previous = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        repo_text
        if not previous
        else repo_text + os.pathsep + previous
    )

    try:
        result = runner(
            [
                str(python_path),
                "-c",
                probe,
            ],
            cwd=str(repo),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=45,
        )
    except Exception as exc:
        return (
            False,
            "Segmentation runtime probe failed: {}".format(
                exc
            ),
        )

    output = (result.stdout or "").strip()

    if result.returncode != 0:
        return (
            False,
            "Segmentation Python started but imports failed: {}".format(
                output.splitlines()[-1]
                if output
                else "unknown error"
            ),
        )

    try:
        info = json.loads(output.splitlines()[-1])
    except Exception:
        return (
            False,
            "Segmentation runtime returned unexpected output: {}".format(
                output[:300]
            ),
        )

    python_version = tuple(info.get("python", (0, 0)))

    if python_version < (3, 10):
        return (
            False,
            "Segmentation Python must be >= 3.10; found {}.{}".format(
                *python_version
            ),
        )

    if not info.get("cuda"):
        return (
            False,
            "PyTorch CUDA is unavailable in the segmentation environment.",
        )

    detail = "Python {}.{}, PyTorch {}, CUDA {}, GPU {}".format(
        python_version[0],
        python_version[1],
        info.get("torch", "unknown"),
        info.get("cuda"),
        info.get("gpu", "unknown"),
    )

    return True, detail


def resolve_segmentation_runtime(
    root,
    config_path=None,
):
    root = Path(root)
    config_path = (
        Path(config_path)
        if config_path
        else root / "config" / DEFAULT_CONFIG_NAME
    )

    config = load_segmentation_config(
        config_path
    )

    if not config:
        raise RuntimeError(
            "Segmentation config is missing or empty: {}"
            .format(config_path)
        )

    runtime = resolve_config_paths(
        config,
        root,
    )
    runtime["python"] = ensure_environment(root, "seg")

    ok, detail = validate_segmentation_runtime(
        runtime
    )

    if not ok:
        raise RuntimeError(detail)

    runtime["detail"] = detail
    runtime["config_path"] = config_path

    return runtime
