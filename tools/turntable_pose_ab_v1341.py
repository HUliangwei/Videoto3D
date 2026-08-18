"""V1.3.4.1 Turntable pose A/B benchmark.

This diagnostic tool reuses one existing COLMAP database and compares two
free-span Turntable pose trajectories:

* legacy generic-essential rotation magnitudes;
* V1.3.4 constrained one-axis Turntable fits.

It never writes to ``colmap/sparse/0``.  All known-pose models, triangulated
candidates, logs, and the JSON report live below
``colmap/diagnostics/pose_ab_v1341``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path


def benchmark_paths(run_root):
    run_root = Path(run_root)
    root = run_root / "colmap" / "diagnostics" / "pose_ab_v1341"
    return {
        "root": root,
        "report": root / "pose_ab_report.json",
        "logs": root / "logs",
        "legacy": root / "legacy",
        "constrained": root / "constrained",
    }


def estimator_summary(
    name,
    span_deg,
    constraint_count,
    gap_coverage_ratio,
    candidates,
    selected,
):
    return {
        "estimator": str(name),
        "span_deg": float(span_deg),
        "constraint_count": int(constraint_count),
        "gap_coverage_ratio": float(gap_coverage_ratio),
        "best_direction": selected.get("direction"),
        "selected_model": selected.get("model"),
        "selected_stats": dict(selected.get("stats", {})),
        "candidate_stats": {
            item.get("direction"): dict(item.get("stats", {}))
            for item in candidates
        },
    }


def _number(stats, key):
    value = (stats or {}).get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_sparse_stats(legacy, constrained):
    legacy_stats = (legacy or {}).get("selected_stats", {})
    constrained_stats = (constrained or {}).get("selected_stats", {})

    legacy_points = _number(legacy_stats, "points3D")
    constrained_points = _number(constrained_stats, "points3D")
    legacy_track = _number(legacy_stats, "mean_track_length")
    constrained_track = _number(constrained_stats, "mean_track_length")
    legacy_error = _number(legacy_stats, "mean_reprojection_error")
    constrained_error = _number(constrained_stats, "mean_reprojection_error")

    points_delta = None
    points_ratio = None
    if legacy_points is not None and constrained_points is not None:
        points_delta = constrained_points - legacy_points
        if legacy_points > 0:
            points_ratio = constrained_points / legacy_points

    track_delta = None
    if legacy_track is not None and constrained_track is not None:
        track_delta = constrained_track - legacy_track

    error_delta = None
    if legacy_error is not None and constrained_error is not None:
        error_delta = constrained_error - legacy_error

    return {
        "points3D_delta": None if points_delta is None else int(round(points_delta)),
        "points3D_ratio": points_ratio,
        "mean_track_length_delta": track_delta,
        "mean_reprojection_error_delta": error_delta,
        "constrained_improves_points": bool(points_delta is not None and points_delta > 0),
        "constrained_improves_track_length": bool(track_delta is not None and track_delta > 0),
    }


def _resolve_colmap_path(project_root, explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    for key in ("VIDEOTO3D_COLMAP", "COLMAP_PATH"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))

    found = shutil.which("colmap") or shutil.which("COLMAP.bat")
    if found:
        candidates.append(Path(found))

    # Current Videoto3D Windows development layout.  This is a fallback only;
    # --colmap and PATH always win.
    candidates.extend(
        [
            Path("C:/colmap/colmap-x64-windows-cuda/COLMAP.bat"),
            Path("C:/colmap/COLMAP.bat"),
        ]
    )

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            resolved = candidate.expanduser()
        if resolved.exists():
            return resolved

    raise FileNotFoundError(
        "COLMAP not found. Pass --colmap C:/path/to/COLMAP.bat or put colmap on PATH."
    )


def _trajectory_from_constraints(constraints, frame_count):
    from pipeline.workflows.turntable.legacy_v13.angle import cumulative_angles_from_increments, solve_free_span_increments

    solved = solve_free_span_increments(constraints, frame_count)
    angles = cumulative_angles_from_increments(solved["increments_rad"])
    return {
        "angles_rad": angles,
        "span_deg": math.degrees(float(angles[-1])),
        "constraint_count": int(solved["constraint_count"]),
        "gap_coverage_ratio": float(solved["gap_coverage_ratio"]),
        "median_abs_residual_deg": math.degrees(float(solved["median_abs_residual_rad"])),
        "max_abs_residual_deg": math.degrees(float(solved["max_abs_residual_rad"])),
    }


def _triangulate_estimator(
    name,
    angles_rad,
    project_root,
    run_root,
    colmap_path,
    camera,
    images,
    tvec,
    estimator_root,
    logs_root,
):
    from pipeline.workflows.turntable.legacy_v13.reconstruction import (
        _parse_analyzer_stats,
        _run_stage,
        _triangulator_args,
        _valid_binary_model,
        build_pose_records,
        choose_turntable_candidate,
        write_known_pose_model,
    )

    frames_dir = run_root / "frames"
    database_path = run_root / "colmap" / "database.db"
    candidates = []

    for label, sign in (("cw", 1), ("ccw", -1)):
        known_model = estimator_root / "known" / label
        candidate_model = estimator_root / "models" / label
        write_known_pose_model(
            known_model,
            camera,
            build_pose_records(images, tvec, angles_rad, sign),
        )
        candidate_model.mkdir(parents=True, exist_ok=True)
        _run_stage(
            colmap_path,
            _triangulator_args(database_path, frames_dir, known_model, candidate_model),
            logs_root / f"{name}_point_triangulator_{label}.log",
            run_root / "colmap",
        )
        if not _valid_binary_model(candidate_model):
            raise RuntimeError(f"Incomplete {name}/{label} triangulated model: {candidate_model}")
        analyzer = _run_stage(
            colmap_path,
            ["model_analyzer", "--path", str(candidate_model)],
            logs_root / f"{name}_model_analyzer_{label}.log",
            run_root / "colmap",
        )
        candidates.append(
            {
                "direction": label,
                "direction_sign": sign,
                "model": str(candidate_model),
                "stats": _parse_analyzer_stats(analyzer),
            }
        )

    selected = choose_turntable_candidate(candidates)
    return candidates, selected


def run_pose_ab_benchmark(project_root, run_id, colmap_path=None, overwrite=True):
    from pipeline.workflows.turntable.legacy_v13.reconstruction import estimate_turntable_translation, read_database_scene
    from pipeline.workflows.turntable.legacy_v13.angle import (
        read_pair_rotation_constraints,
        read_turntable_constrained_constraints,
    )

    project_root = Path(project_root).resolve()
    run_root = project_root / "workspace" / "runs" / str(run_id)
    database_path = run_root / "colmap" / "database.db"
    frames_dir = run_root / "frames"
    masks_dir = run_root / "masks"

    if not database_path.exists():
        raise FileNotFoundError(f"COLMAP database not found: {database_path}")
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    if not masks_dir.exists():
        raise FileNotFoundError(f"Masks directory not found: {masks_dir}")

    paths = benchmark_paths(run_root)
    if overwrite and paths["root"].exists():
        shutil.rmtree(paths["root"])
    paths["logs"].mkdir(parents=True, exist_ok=True)

    resolved_colmap = _resolve_colmap_path(project_root, colmap_path)
    camera, images = read_database_scene(database_path)
    center = estimate_turntable_translation(masks_dir, images, camera)
    tvec = tuple(float(value) for value in center["tvec"])

    legacy_constraints = read_pair_rotation_constraints(
        database_path,
        images,
        camera,
        min_inliers=12,
        max_gap=10,
        max_step_rotation_deg=20.0,
    )
    constrained_result = read_turntable_constrained_constraints(
        database_path,
        images,
        camera,
        tvec,
        min_inliers=12,
        max_gap=10,
        max_step_rotation_deg=20.0,
        max_model_error_px=3.0,
    )
    constrained_constraints = constrained_result["constraints"]

    if len(legacy_constraints) < 3:
        raise RuntimeError(f"Legacy benchmark needs >=3 constraints; found {len(legacy_constraints)}.")
    if len(constrained_constraints) < 3:
        raise RuntimeError(
            f"Constrained benchmark needs >=3 constraints; found {len(constrained_constraints)}."
        )

    legacy_trajectory = _trajectory_from_constraints(legacy_constraints, len(images))
    constrained_trajectory = _trajectory_from_constraints(constrained_constraints, len(images))

    legacy_candidates, legacy_selected = _triangulate_estimator(
        "legacy",
        legacy_trajectory["angles_rad"],
        project_root,
        run_root,
        resolved_colmap,
        camera,
        images,
        tvec,
        paths["legacy"],
        paths["logs"],
    )
    constrained_candidates, constrained_selected = _triangulate_estimator(
        "constrained",
        constrained_trajectory["angles_rad"],
        project_root,
        run_root,
        resolved_colmap,
        camera,
        images,
        tvec,
        paths["constrained"],
        paths["logs"],
    )

    legacy_summary = estimator_summary(
        "legacy_generic_essential",
        legacy_trajectory["span_deg"],
        legacy_trajectory["constraint_count"],
        legacy_trajectory["gap_coverage_ratio"],
        legacy_candidates,
        legacy_selected,
    )
    legacy_summary["graph_median_abs_residual_deg"] = legacy_trajectory["median_abs_residual_deg"]
    legacy_summary["graph_max_abs_residual_deg"] = legacy_trajectory["max_abs_residual_deg"]

    constrained_summary = estimator_summary(
        "turntable_constrained_essential_v134",
        constrained_trajectory["span_deg"],
        constrained_trajectory["constraint_count"],
        constrained_trajectory["gap_coverage_ratio"],
        constrained_candidates,
        constrained_selected,
    )
    constrained_summary["graph_median_abs_residual_deg"] = constrained_trajectory["median_abs_residual_deg"]
    constrained_summary["graph_max_abs_residual_deg"] = constrained_trajectory["max_abs_residual_deg"]
    accepted_errors = [
        float(item["model_error_px"])
        for item in constrained_constraints
        if item.get("model_error_px") is not None
    ]
    if accepted_errors:
        accepted_errors.sort()
        middle = len(accepted_errors) // 2
        if len(accepted_errors) % 2:
            median_error = accepted_errors[middle]
        else:
            median_error = 0.5 * (accepted_errors[middle - 1] + accepted_errors[middle])
        constrained_summary["median_model_residual_px"] = median_error
        constrained_summary["max_model_residual_px"] = max(accepted_errors)

    report = {
        "version": "1.3.4.1",
        "purpose": "pose_ab_benchmark",
        "run_id": str(run_id),
        "database": str(database_path),
        "shared_sparse_untouched": str(run_root / "colmap" / "sparse" / "0"),
        "diagnostics_root": str(paths["root"]),
        "image_count": len(images),
        "rotation_center_tvec": [float(value) for value in tvec],
        "legacy": legacy_summary,
        "constrained": constrained_summary,
        "comparison": compare_sparse_stats(legacy_summary, constrained_summary),
    }
    paths["report"].write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report, paths["report"]


def _print_compact(report, report_path):
    compact = {
        "run_id": report["run_id"],
        "legacy": report["legacy"],
        "constrained": report["constrained"],
        "comparison": report["comparison"],
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_path}")
    print("Shared sparse/0 was not modified.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare legacy and constrained Turntable pose trajectories on one COLMAP database.")
    parser.add_argument("--run", required=True, help="Existing Videoto3D run id, e.g. hlw_04")
    parser.add_argument("--colmap", default=None, help="Optional explicit path to colmap/COLMAP.bat")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not replace an existing diagnostics/pose_ab_v1341 directory")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    report, report_path = run_pose_ab_benchmark(
        project_root,
        args.run,
        colmap_path=args.colmap,
        overwrite=not args.no_overwrite,
    )
    _print_compact(report, report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
