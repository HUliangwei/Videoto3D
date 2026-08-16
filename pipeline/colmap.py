import os
import re
import shutil
import subprocess
from pathlib import Path

from pipeline.processes import launch_detached


def build_feature_extractor_args(database_path, image_path, mask_path=None):
    args = [
        "feature_extractor",
        "--database_path", str(Path(database_path)),
        "--image_path", str(Path(image_path)),
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", "SIMPLE_RADIAL",
        "--FeatureExtraction.use_gpu", "1",
    ]

    if mask_path is not None:
        args.extend([
            "--ImageReader.mask_path", str(Path(mask_path)),
        ])

    return args


def build_sequential_matcher_args(database_path):
    return [
        "sequential_matcher",
        "--database_path", str(Path(database_path)),
        "--SequentialMatching.overlap", "10",
        "--SequentialMatching.quadratic_overlap", "1",
        "--FeatureMatching.use_gpu", "1",
    ]


def build_mapper_args(database_path, image_path, sparse_path):
    return [
        "mapper",
        "--database_path", str(Path(database_path)),
        "--image_path", str(Path(image_path)),
        "--output_path", str(Path(sparse_path)),
        "--Mapper.multiple_models", "0",
    ]


def build_model_analyzer_args(model_path):
    return [
        "model_analyzer",
        "--path", str(Path(model_path)),
    ]


def build_gui_args(model_path, database_path, image_path):
    return [
        "gui",
        "--import_path", str(Path(model_path)),
        "--database_path", str(Path(database_path)),
        "--image_path", str(Path(image_path)),
    ]



def prepare_gui_model(model_path, viewer_model_path):
    """Create a clean COLMAP model directory for GUI import.

    Mapper output may contain project.ini with mapper-only keys such as
    input_path/output_path. The GUI import only needs the three binary model
    files, so stage those files separately to avoid loading mapper config noise.
    """
    model_path = Path(model_path)
    viewer_model_path = Path(viewer_model_path)
    required = ("cameras.bin", "images.bin", "points3D.bin")

    missing = [name for name in required if not (model_path / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Sparse model is incomplete. Missing: {}".format(
                ", ".join(str(model_path / name) for name in missing)
            )
        )

    if viewer_model_path.exists():
        shutil.rmtree(viewer_model_path)
    viewer_model_path.mkdir(parents=True, exist_ok=True)

    for name in required:
        shutil.copy2(model_path / name, viewer_model_path / name)

    return str(viewer_model_path)

def launch_colmap_gui(
    colmap_path,
    model_path,
    database_path,
    image_path,
    cwd=None,
):
    colmap_path = Path(colmap_path)
    model_path = Path(model_path)
    database_path = Path(database_path)
    image_path = Path(image_path)

    if not colmap_path.exists():
        raise FileNotFoundError(
            "COLMAP not found: {}".format(colmap_path)
        )

    required_model_files = (
        model_path / "cameras.bin",
        model_path / "images.bin",
        model_path / "points3D.bin",
    )

    missing = [
        str(path)
        for path in required_model_files
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Sparse model is incomplete. Missing: {}".format(
                ", ".join(missing)
            )
        )

    if not database_path.exists():
        raise FileNotFoundError(
            "COLMAP database not found: {}".format(database_path)
        )

    if not image_path.exists():
        raise FileNotFoundError(
            "Image directory not found: {}".format(image_path)
        )

    viewer_model_path = model_path.parent.parent / "viewer_model"
    clean_model_path = Path(prepare_gui_model(model_path, viewer_model_path))

    args = build_gui_args(
        model_path=clean_model_path,
        database_path=database_path,
        image_path=image_path,
    )

    command = _build_colmap_command(
        colmap_path,
        args,
    )

    process = launch_detached(
        command,
        cwd=cwd or model_path.parent,
    )

    return process.pid


def _build_colmap_command(colmap_path, args):
    colmap_path = Path(colmap_path)

    if colmap_path.suffix.lower() in (".bat", ".cmd"):
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(colmap_path),
        ] + list(args)

    return [str(colmap_path)] + list(args)


def _run_stage(colmap_path, args, log_path, cwd):
    command = _build_colmap_command(
        colmap_path,
        args,
    )

    result = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )

    log_path = Path(log_path)
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    log_path.write_text(
        result.stdout or "",
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "COLMAP stage '{}' failed with exit code {}. See {}".format(
                args[0],
                result.returncode,
                log_path,
            )
        )

    return result.stdout or ""


def _find_sparse_models(sparse_dir):
    sparse_dir = Path(sparse_dir)

    models = []

    if not sparse_dir.exists():
        return models

    for candidate in sorted(
        [p for p in sparse_dir.iterdir() if p.is_dir()],
        key=lambda p: (
            0,
            int(p.name),
        ) if p.name.isdigit() else (
            1,
            p.name,
        ),
    ):
        required = (
            candidate / "cameras.bin",
            candidate / "images.bin",
            candidate / "points3D.bin",
        )

        if all(path.exists() for path in required):
            models.append(candidate)

    return models


def _parse_analyzer_stats(text):
    stats = {}

    patterns = {
        "registered_images": [
            r"Registered images:\s*(\d+)",
            r"Images:\s*(\d+)",
        ],
        "points3D": [
            r"Points:\s*(\d+)",
            r"3D points:\s*(\d+)",
        ],
        "mean_track_length": [
            r"Mean track length:\s*([0-9.]+)",
        ],
        "mean_reprojection_error": [
            r"Mean reprojection error:\s*([0-9.]+)",
        ],
    }

    for key, candidates in patterns.items():
        for pattern in candidates:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            if match:
                value = match.group(1)
                stats[key] = (
                    int(value)
                    if key in ("registered_images", "points3D")
                    else float(value)
                )
                break

    return stats


def run_sparse_reconstruction(
    colmap_path,
    frames_dir,
    colmap_dir,
    logs_dir,
    overwrite=True,
    mask_path=None,
):
    colmap_path = Path(colmap_path)
    frames_dir = Path(frames_dir)
    colmap_dir = Path(colmap_dir)
    logs_dir = Path(logs_dir)
    mask_path = Path(mask_path) if mask_path is not None else None

    if not colmap_path.exists():
        raise FileNotFoundError(
            "COLMAP not found: {}".format(colmap_path)
        )

    if mask_path is not None and not mask_path.exists():
        raise FileNotFoundError(
            "COLMAP mask directory not found: {}".format(mask_path)
        )

    frame_count = len(
        list(frames_dir.glob("frame_*.jpg"))
    )

    if frame_count < 10:
        raise RuntimeError(
            "Need at least 10 extracted frames before sparse reconstruction. "
            "Found {} in {}".format(
                frame_count,
                frames_dir,
            )
        )

    colmap_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    logs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_path = colmap_dir / "database.db"
    sparse_dir = colmap_dir / "sparse"

    if overwrite:
        if database_path.exists():
            database_path.unlink()

        if sparse_dir.exists():
            shutil.rmtree(sparse_dir)

    sparse_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    feature_output = _run_stage(
        colmap_path,
        build_feature_extractor_args(
            database_path,
            frames_dir,
            mask_path=mask_path,
        ),
        logs_dir / "colmap_feature_extractor.log",
        colmap_dir,
    )

    matcher_output = _run_stage(
        colmap_path,
        build_sequential_matcher_args(
            database_path,
        ),
        logs_dir / "colmap_sequential_matcher.log",
        colmap_dir,
    )

    mapper_output = _run_stage(
        colmap_path,
        build_mapper_args(
            database_path,
            frames_dir,
            sparse_dir,
        ),
        logs_dir / "colmap_mapper.log",
        colmap_dir,
    )

    models = _find_sparse_models(
        sparse_dir
    )

    if not models:
        raise RuntimeError(
            "COLMAP mapper completed but no valid sparse model was found in {}. "
            "See {}".format(
                sparse_dir,
                logs_dir / "colmap_mapper.log",
            )
        )

    model_path = models[0]

    analyzer_output = _run_stage(
        colmap_path,
        build_model_analyzer_args(
            model_path,
        ),
        logs_dir / "colmap_model_analyzer.log",
        colmap_dir,
    )

    stats = _parse_analyzer_stats(
        analyzer_output
    )

    return {
        "frame_count": frame_count,
        "database": str(database_path),
        "mask_path": str(mask_path) if mask_path is not None else None,
        "sparse_dir": str(sparse_dir),
        "model": str(model_path),
        "model_count": len(models),
        "stats": stats,
        "logs": {
            "feature_extractor": str(
                logs_dir / "colmap_feature_extractor.log"
            ),
            "sequential_matcher": str(
                logs_dir / "colmap_sequential_matcher.log"
            ),
            "mapper": str(
                logs_dir / "colmap_mapper.log"
            ),
            "model_analyzer": str(
                logs_dir / "colmap_model_analyzer.log"
            ),
        },
    }
