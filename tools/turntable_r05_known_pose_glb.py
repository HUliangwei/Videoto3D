"""Turntable R0.5 known-pose COLMAP -> OpenMVS -> GLB fast route."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _resolve_colmap(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("VIDEOTO3D_COLMAP")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(r"C:\colmap\colmap-x64-windows-cuda\COLMAP.bat"))
    which = shutil.which("colmap")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "COLMAP not found. Pass --colmap or set VIDEOTO3D_COLMAP."
    )


def _resolve_openmvs_bin(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("VIDEOTO3D_OPENMVS_BIN")
    if env:
        candidates.append(Path(env))
    interface = shutil.which("InterfaceCOLMAP")
    if interface:
        candidates.append(Path(interface).parent)
    for path in candidates:
        if (
            path.exists()
            and (
                (path / "InterfaceCOLMAP.exe").exists()
                or (path / "InterfaceCOLMAP").exists()
            )
        ):
            return path
    raise FileNotFoundError(
        "OpenMVS bin not found. Pass --openmvs-bin or set "
        "VIDEOTO3D_OPENMVS_BIN to the folder containing InterfaceCOLMAP."
    )


def _resolve_blender(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("VIDEOTO3D_BLENDER")
    if env:
        candidates.append(Path(env))
    candidates.append(
        Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
    )
    which = shutil.which("blender")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Blender not found. Pass --blender or set VIDEOTO3D_BLENDER."
    )


def _colmap_command(colmap_path, args):
    colmap_path = Path(colmap_path)
    if colmap_path.suffix.lower() in (".bat", ".cmd"):
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d", "/c", str(colmap_path),
        ] + list(args)
    return [str(colmap_path)] + list(args)


def _run_logged(command, cwd, log_path):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed with exit code {}. See {}".format(
                result.returncode, log_path
            )
        )


def _prepare_image_list_and_masks(dataset, frames, work_root):
    image_list = work_root / "image_list.txt"
    names = [str(frame["frame"]).replace("\\", "/") for frame in frames]
    image_list.write_text("\n".join(names) + "\n", encoding="utf-8")

    mask_root = work_root / "feature_masks"
    if mask_root.exists():
        shutil.rmtree(mask_root)
    mask_root.mkdir(parents=True)

    copied = 0
    for frame, name in zip(frames, names):
        mask_rel = frame.get("mask")
        if not mask_rel:
            continue
        source = dataset / str(mask_rel)
        if not source.exists():
            continue
        target = mask_root / (name + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return image_list, mask_root if copied == len(frames) else None, names


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Turntable R0.5 fast GLB route: known-pose COLMAP, "
            "existing OpenMVS mesh pipeline, Blender GLB export."
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--orbit-report", required=True)
    parser.add_argument("--colmap")
    parser.add_argument("--openmvs-bin")
    parser.add_argument("--blender")
    parser.add_argument("--output-dir")
    parser.add_argument("--sequential-overlap", type=int, default=8)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset).resolve()
    gt_path = dataset / "ground_truth.json"
    if not gt_path.exists():
        raise SystemExit("ground_truth.json missing: {}".format(gt_path))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    frames = gt["frames"]

    orbit_path = Path(args.orbit_report).resolve()
    orbit_doc = json.loads(orbit_path.read_text(encoding="utf-8"))
    angles = orbit_doc["global_orbit"]["angles_deg"]
    shared = orbit_doc["shared_geometry"]
    if len(angles) != len(frames):
        raise SystemExit("Orbit frame count does not match dataset")

    from pipeline.workflows.turntable.pose.synthetic_geometry import (
        camera_intrinsics_from_ground_truth,
    )
    from pipeline.workflows.turntable.geometry.known_pose_colmap import (
        feature_extractor_args,
        point_triangulator_args,
        sequential_matcher_args,
        write_known_pose_text_model,
    )

    intrinsics = camera_intrinsics_from_ground_truth(gt["camera"])
    width, height = [int(v) for v in gt["camera"]["resolution"]]

    if args.output_dir:
        work_root = Path(args.output_dir).resolve()
    else:
        work_root = (
            dataset.parent.parent / "r05" / dataset.name
        ).resolve()

    if work_root.exists() and args.overwrite:
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    colmap_path = _resolve_colmap(args.colmap)
    openmvs_bin = _resolve_openmvs_bin(args.openmvs_bin)
    blender_path = _resolve_blender(args.blender)

    colmap_dir = work_root / "colmap"
    logs_dir = work_root / "logs"
    openmvs_dir = work_root / "openmvs"
    output_dir = work_root / "output"
    database = colmap_dir / "database.db"
    known_model = colmap_dir / "known_pose_text"
    triangulated = colmap_dir / "triangulated"
    for path in (colmap_dir, logs_dir, openmvs_dir, output_dir):
        path.mkdir(parents=True, exist_ok=True)

    if database.exists():
        if args.overwrite:
            database.unlink()
        else:
            raise SystemExit(
                "R0.5 database already exists. Use --overwrite to restart: "
                + str(database)
            )

    image_list, mask_root, image_names = _prepare_image_list_and_masks(
        dataset, frames, colmap_dir
    )

    started = time.perf_counter()
    feature_args = feature_extractor_args(
        database_path=database,
        image_path=dataset,
        image_list_path=image_list,
        intrinsics=intrinsics,
        mask_path=mask_root,
    )
    _run_logged(
        _colmap_command(colmap_path, feature_args),
        work_root,
        logs_dir / "01_feature_extractor.log",
    )

    matcher_args = sequential_matcher_args(
        database,
        overlap=args.sequential_overlap,
    )
    _run_logged(
        _colmap_command(colmap_path, matcher_args),
        work_root,
        logs_dir / "02_sequential_matcher.log",
    )

    write_known_pose_text_model(
        database_path=database,
        output_dir=known_model,
        image_names=image_names,
        angles_deg=angles,
        axis=shared["axis_cv"],
        transverse_direction=shared["transverse_orbit_direction_cv"],
        intrinsics=intrinsics,
        width=width,
        height=height,
    )

    if triangulated.exists():
        shutil.rmtree(triangulated)
    triangulated.mkdir(parents=True)
    triangulator_args = point_triangulator_args(
        database_path=database,
        image_path=dataset,
        input_path=known_model,
        output_path=triangulated,
    )
    _run_logged(
        _colmap_command(colmap_path, triangulator_args),
        work_root,
        logs_dir / "03_point_triangulator.log",
    )

    # Reuse the already validated production mesh route.
    from pipeline.openmvs import run_mesh_pipeline
    run_mesh_pipeline(
        colmap_path=colmap_path,
        openmvs_bin=openmvs_bin,
        frames_dir=dataset,
        sparse_model=triangulated,
        colmap_dir=colmap_dir / "mesh_workspace",
        openmvs_dir=openmvs_dir,
        logs_dir=logs_dir,
        overwrite=True,
        mask_path=None,
        profile=None,
    )

    obj_path = openmvs_dir / "object.obj"
    if not obj_path.exists() or obj_path.stat().st_size == 0:
        raise RuntimeError(
            "OpenMVS completed without a usable object.obj: {}".format(obj_path)
        )

    from pipeline.blender import export_obj_to_glb
    glb_path = output_dir / "turntable.glb"
    blender_script = ROOT / "scripts" / "blender_export_glb.py"
    export_result = export_obj_to_glb(
        blender_path=blender_path,
        script_path=blender_script,
        input_obj=obj_path,
        output_glb=glb_path,
        working_dir=work_root,
        log_path=logs_dir / "04_blender_export.log",
    )

    elapsed = time.perf_counter() - started
    report = {
        "schema_version": 1,
        "stage": "turntable_r05_known_pose_fast_glb",
        "dataset": str(dataset),
        "orbit_report": str(orbit_path),
        "pose_contract": {
            "ground_truth_angles_used": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
            "virtual_orbit_scale": 1.0,
        },
        "tools": {
            "colmap": str(colmap_path),
            "openmvs_bin": str(openmvs_bin),
            "blender": str(blender_path),
        },
        "artifacts": {
            "database": str(database),
            "known_pose_model": str(known_model),
            "triangulated_model": str(triangulated),
            "openmvs_obj": str(obj_path),
            "glb": str(glb_path),
        },
        "glb_size_bytes": int(export_result["size_bytes"]),
        "runtime_sec": float(elapsed),
    }
    report_path = work_root / "r05_fast_glb_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 68)
    print("Turntable R0.5 FAST GLB COMPLETE")
    print("GLB    :", glb_path)
    print("Size   :", export_result["size_bytes"], "bytes")
    print("Report :", report_path)
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
