"""Brush Gaussian Splat adapter for run-local Videoto3D datasets."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from pipeline.processes import launch_detached
from pipeline.colmap_object import filter_colmap_points_by_masks

DEFAULT_STEPS = 30000
DEFAULT_MAX_SPLATS = 2_000_000
DEFAULT_MAX_RESOLUTION = 1280
DEFAULT_EXPORT_EVERY = 5000
_REQUIRED_SPARSE_FILES = ("cameras.bin", "images.bin", "points3D.bin")
_EXPORT_RE = re.compile(r"_(\d+)\.ply$", re.IGNORECASE)


def _link_or_copy(source, target):
    source = Path(source)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    try:
        os.link(str(source), str(target))
    except OSError:
        shutil.copy2(str(source), str(target))


def prepare_brush_dataset(
    run_root,
    foreground_ratio=0.60,
    min_foreground_observations=2,
    min_kept_points=300,
):
    run_root = Path(run_root)
    frames_dir = run_root / "frames"
    masks_dir = run_root / "masks"
    sparse_src = run_root / "colmap" / "sparse" / "0"
    brush_root = run_root / "splat"
    dataset_root = brush_root / "dataset"

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        raise FileNotFoundError("Brush staging requires extracted RGB frames: {}".format(frames_dir))

    missing_sparse = [name for name in _REQUIRED_SPARSE_FILES if not (sparse_src / name).exists()]
    if missing_sparse:
        raise FileNotFoundError(
            "Brush staging requires COLMAP sparse/0. Missing: {}".format(", ".join(missing_sparse))
        )

    masks = []
    for frame in frames:
        mask = masks_dir / (frame.name + ".png")
        if not mask.exists():
            raise FileNotFoundError("Brush mask not found for {}: {}".format(frame.name, mask))
        masks.append(mask)

    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    images_out = dataset_root / "images"
    masks_out = dataset_root / "masks"
    sparse_out = dataset_root / "sparse" / "0"
    images_out.mkdir(parents=True, exist_ok=True)
    masks_out.mkdir(parents=True, exist_ok=True)
    sparse_out.mkdir(parents=True, exist_ok=True)

    for frame, mask in zip(frames, masks):
        _link_or_copy(frame, images_out / frame.name)
        _link_or_copy(mask, masks_out / mask.name)
    report_path = brush_root / "object_sparse_report.json"
    object_report = filter_colmap_points_by_masks(
        source_model=sparse_src,
        masks_dir=masks_dir,
        output_model=sparse_out,
        report_path=report_path,
        foreground_ratio=foreground_ratio,
        min_foreground_observations=min_foreground_observations,
        min_kept_points=min_kept_points,
    )

    return {
        "brush_root": str(brush_root),
        "dataset_root": str(dataset_root),
        "image_count": len(frames),
        "mask_count": len(masks),
        "sparse_model": str(sparse_out),
        "object_sparse_report": str(report_path),
        "object_sparse": object_report,
    }


def build_brush_train_command(
    brush_path,
    dataset_root,
    run_id,
    steps=DEFAULT_STEPS,
    max_splats=DEFAULT_MAX_SPLATS,
    max_resolution=DEFAULT_MAX_RESOLUTION,
    export_every=DEFAULT_EXPORT_EVERY,
):
    return [
        str(Path(brush_path)),
        str(Path(dataset_root)),
        "--total-train-iters", str(int(steps)),
        "--max-splats", str(int(max_splats)),
        "--max-resolution", str(int(max_resolution)),
        "--export-every", str(int(export_every)),
        "--export-path", "./exports/",
        "--export-name", f"{run_id}_{{iter}}.ply",
    ]


def build_brush_view_command(brush_path, splat_path):
    return [
        str(Path(brush_path)),
        str(Path(splat_path)),
        "--with-viewer",
    ]


def _stream_process(command, cwd, log_path):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
        returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(
            "Brush training failed with exit code {}. See {}".format(returncode, log_path)
        )


def select_latest_brush_export(exports_dir, run_id):
    exports_dir = Path(exports_dir)
    candidates = []
    for path in exports_dir.glob("{}_*.ply".format(run_id)):
        match = _EXPORT_RE.search(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise RuntimeError("Brush completed but no PLY export was found in {}".format(exports_dir))
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1], candidates[-1][0]


def run_brush_training(
    brush_path,
    run_root,
    run_id,
    steps=DEFAULT_STEPS,
    max_splats=DEFAULT_MAX_SPLATS,
    max_resolution=DEFAULT_MAX_RESOLUTION,
    foreground_ratio=0.60,
    min_foreground_observations=2,
    min_kept_points=300,
):
    brush_path = Path(brush_path)
    run_root = Path(run_root)
    if not brush_path.exists():
        raise FileNotFoundError("Brush not found: {}".format(brush_path))

    staged = prepare_brush_dataset(
        run_root,
        foreground_ratio=foreground_ratio,
        min_foreground_observations=min_foreground_observations,
        min_kept_points=min_kept_points,
    )
    brush_root = Path(staged["brush_root"])
    dataset_root = Path(staged["dataset_root"])
    exports_dir = brush_root / "exports"
    if exports_dir.exists():
        shutil.rmtree(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    command = build_brush_train_command(
        brush_path=brush_path,
        dataset_root=dataset_root,
        run_id=run_id,
        steps=steps,
        max_splats=max_splats,
        max_resolution=max_resolution,
    )
    log_path = run_root / "logs" / "splat" / "brush_train.log"
    _stream_process(command, cwd=brush_root, log_path=log_path)

    latest, iteration = select_latest_brush_export(exports_dir, run_id)
    raw_dir = brush_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_raw = raw_dir / "{}_raw.ply".format(run_id)
    _link_or_copy(latest, canonical_raw)

    recipe = {
        "adapter": "brush",
        "steps": int(steps),
        "max_splats": int(max_splats),
        "max_resolution": int(max_resolution),
        "export_every": DEFAULT_EXPORT_EVERY,
        "dataset": "dataset",
        "final_iteration": int(iteration),
        "final_export": str(latest.relative_to(brush_root)),
        "canonical_raw": str(canonical_raw.relative_to(run_root)),
        "foreground_ratio": float(foreground_ratio),
        "min_foreground_observations": int(min_foreground_observations),
        "object_sparse_report": str(Path(staged["object_sparse_report"]).relative_to(brush_root)),
        "command": command,
    }
    recipe_path = brush_root / "recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        **staged,
        "exports_dir": str(exports_dir),
        "final_checkpoint": str(latest),
        "final_iteration": int(iteration),
        "raw_ply": str(canonical_raw),
        "raw_size_bytes": canonical_raw.stat().st_size,
        # Compatibility alias for older callers; V0.11 treats this as raw, not final.
        "output_ply": str(canonical_raw),
        "size_bytes": canonical_raw.stat().st_size,
        "recipe": str(recipe_path),
        "log": str(log_path),
        "command": command,
    }


def launch_brush_viewer(brush_path, splat_path, working_dir=None):
    brush_path = Path(brush_path)
    splat_path = Path(splat_path)
    if not brush_path.exists():
        raise FileNotFoundError("Brush not found: {}".format(brush_path))
    if not splat_path.exists():
        raise FileNotFoundError("Splat PLY not found: {}".format(splat_path))
    command = build_brush_view_command(brush_path, splat_path)
    process = launch_detached(command, cwd=working_dir or splat_path.parent)
    return process.pid
