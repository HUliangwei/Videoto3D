"""V1.3.5 Turntable Sequential-vs-Exhaustive matching A/B benchmark.

This diagnostic benchmark keeps the current V1.3.4 constrained Turntable pose
estimator fixed and changes only the COLMAP matcher.  The existing run-local
``colmap/database.db`` is the Sequential baseline.  An SQLite backup is made
below ``colmap/diagnostics/matching_ab_v135/exhaustive``; only the copied
``matches`` and ``two_view_geometries`` tables are cleared before COLMAP
``exhaustive_matcher`` repopulates them from the existing keypoints and
descriptors.

The production database and ``colmap/sparse/0`` are never written by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sqlite3
import statistics
import sys
from pathlib import Path


def benchmark_paths(run_root):
    run_root = Path(run_root)
    root = run_root / "colmap" / "diagnostics" / "matching_ab_v135"
    exhaustive = root / "exhaustive"
    return {
        "root": root,
        "report": root / "matching_ab_report.json",
        "logs": root / "logs",
        "sequential": root / "sequential",
        "exhaustive": exhaustive,
        "exhaustive_database": exhaustive / "database.db",
    }


def _table_names(connection):
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def clone_database_for_exhaustive(source_database, destination_database):
    """Create a transactionally consistent feature DB copy without old matches."""
    source_database = Path(source_database)
    destination_database = Path(destination_database)
    if not source_database.exists():
        raise FileNotFoundError(f"COLMAP database not found: {source_database}")
    destination_database.parent.mkdir(parents=True, exist_ok=True)
    if destination_database.exists():
        destination_database.unlink()

    source = sqlite3.connect(str(source_database))
    destination = sqlite3.connect(str(destination_database))
    try:
        source.backup(destination)
        tables = _table_names(destination)
        for table in ("matches", "two_view_geometries"):
            if table in tables:
                destination.execute(f"DELETE FROM {table}")
        destination.commit()
    finally:
        source.close()
        destination.close()
    return destination_database


def database_match_stats(database_path):
    """Return compact counts from COLMAP raw and geometrically verified matches."""
    database_path = Path(database_path)
    connection = sqlite3.connect(str(database_path))
    try:
        tables = _table_names(connection)
        result = {
            "raw_match_pairs": 0,
            "raw_matches": 0,
            "verified_pairs": 0,
            "verified_inliers": 0,
        }
        if "matches" in tables:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(rows),0) FROM matches WHERE rows>0"
            ).fetchone()
            result["raw_match_pairs"] = int(row[0] or 0)
            result["raw_matches"] = int(row[1] or 0)
        if "two_view_geometries" in tables:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(rows),0) FROM two_view_geometries WHERE rows>0"
            ).fetchone()
            result["verified_pairs"] = int(row[0] or 0)
            result["verified_inliers"] = int(row[1] or 0)
        return result
    finally:
        connection.close()


def exhaustive_matcher_args(database_path):
    return [
        "exhaustive_matcher",
        "--database_path", str(database_path),
        "--FeatureMatching.guided_matching", "1",
        "--FeatureMatching.use_gpu", "1",
    ]


def _number(mapping, key):
    value = (mapping or {}).get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(left, right):
    if left is None or right is None:
        return None
    return right - left


def compare_matching_results(sequential, exhaustive):
    seq_matching = (sequential or {}).get("matching", {})
    ex_matching = (exhaustive or {}).get("matching", {})
    seq_pose = (sequential or {}).get("pose", {})
    ex_pose = (exhaustive or {}).get("pose", {})
    seq_stats = (sequential or {}).get("selected_stats", {})
    ex_stats = (exhaustive or {}).get("selected_stats", {})

    seq_points = _number(seq_stats, "points3D")
    ex_points = _number(ex_stats, "points3D")
    points_ratio = None
    if seq_points is not None and ex_points is not None and seq_points > 0:
        points_ratio = ex_points / seq_points

    coverage_delta = _delta(
        _number(seq_pose, "gap_coverage_ratio"),
        _number(ex_pose, "gap_coverage_ratio"),
    )
    adjacent_delta = _delta(
        _number(seq_pose, "adjacent_coverage_ratio"),
        _number(ex_pose, "adjacent_coverage_ratio"),
    )
    track_delta = _delta(
        _number(seq_stats, "mean_track_length"),
        _number(ex_stats, "mean_track_length"),
    )
    error_delta = _delta(
        _number(seq_stats, "mean_reprojection_error"),
        _number(ex_stats, "mean_reprojection_error"),
    )
    points_delta = _delta(seq_points, ex_points)

    return {
        "verified_pairs_delta": int(ex_matching.get("verified_pairs", 0)) - int(seq_matching.get("verified_pairs", 0)),
        "verified_inliers_delta": int(ex_matching.get("verified_inliers", 0)) - int(seq_matching.get("verified_inliers", 0)),
        "constraint_count_delta": int(ex_pose.get("constraint_count", 0)) - int(seq_pose.get("constraint_count", 0)),
        "gap_coverage_ratio_delta": coverage_delta,
        "adjacent_coverage_ratio_delta": adjacent_delta,
        "span_deg_delta": _delta(_number(seq_pose, "span_deg"), _number(ex_pose, "span_deg")),
        "points3D_delta": None if points_delta is None else int(round(points_delta)),
        "points3D_ratio": points_ratio,
        "mean_track_length_delta": track_delta,
        "mean_reprojection_error_delta": error_delta,
        "exhaustive_improves_coverage": bool(coverage_delta is not None and coverage_delta > 0),
        "exhaustive_improves_adjacent_coverage": bool(adjacent_delta is not None and adjacent_delta > 0),
        "exhaustive_improves_points": bool(points_delta is not None and points_delta > 0),
        "exhaustive_improves_track_length": bool(track_delta is not None and track_delta > 0),
    }


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_colmap_path(explicit=None):
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


def _triangulate_database(
    label,
    database_path,
    run_root,
    colmap_path,
    camera,
    images,
    tvec,
    angles_rad,
    output_root,
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

    candidates = []
    frames_dir = run_root / "frames"
    for direction, sign in (("cw", 1), ("ccw", -1)):
        known_model = output_root / "known" / direction
        candidate_model = output_root / "models" / direction
        write_known_pose_model(
            known_model,
            camera,
            build_pose_records(images, tvec, angles_rad, sign),
        )
        candidate_model.mkdir(parents=True, exist_ok=True)
        _run_stage(
            colmap_path,
            _triangulator_args(database_path, frames_dir, known_model, candidate_model),
            logs_root / f"{label}_point_triangulator_{direction}.log",
            run_root / "colmap",
        )
        if not _valid_binary_model(candidate_model):
            raise RuntimeError(f"Incomplete {label}/{direction} model: {candidate_model}")
        analyzer = _run_stage(
            colmap_path,
            ["model_analyzer", "--path", str(candidate_model)],
            logs_root / f"{label}_model_analyzer_{direction}.log",
            run_root / "colmap",
        )
        candidates.append(
            {
                "direction": direction,
                "direction_sign": sign,
                "model": str(candidate_model),
                "stats": _parse_analyzer_stats(analyzer),
            }
        )
    return candidates, choose_turntable_candidate(candidates)


def _evaluate_database(
    label,
    database_path,
    run_root,
    colmap_path,
    tvec,
    output_root,
    logs_root,
):
    from pipeline.workflows.turntable.legacy_v13.reconstruction import read_database_scene
    from pipeline.workflows.turntable.legacy_v13.angle import read_turntable_constrained_constraints

    camera, images = read_database_scene(database_path)
    fitted = read_turntable_constrained_constraints(
        database_path,
        images,
        camera,
        tvec,
        min_inliers=12,
        max_gap=10,
        max_step_rotation_deg=20.0,
        max_model_error_px=3.0,
    )
    constraints = fitted["constraints"]
    if len(constraints) < 3:
        raise RuntimeError(
            f"{label} matching produced only {len(constraints)} constrained pose edges; need >=3."
        )
    trajectory = _trajectory_from_constraints(constraints, len(images))
    adjacent_pairs = len({
        (int(item["left"]), int(item["right"]))
        for item in constraints
        if int(item.get("gap", 0)) == 1
    })
    adjacent_coverage = adjacent_pairs / float(max(1, len(images) - 1))
    model_errors = [
        float(item["model_error_px"])
        for item in constraints
        if item.get("model_error_px") is not None
    ]
    direction_counts = {"positive": 0, "negative": 0}
    for item in constraints:
        if int(item.get("direction_sign", 0)) > 0:
            direction_counts["positive"] += 1
        elif int(item.get("direction_sign", 0)) < 0:
            direction_counts["negative"] += 1

    candidates, selected = _triangulate_database(
        label,
        database_path,
        run_root,
        colmap_path,
        camera,
        images,
        tvec,
        trajectory["angles_rad"],
        output_root,
        logs_root,
    )
    pose = {
        "estimator": "turntable_constrained_essential_v134",
        "span_deg": trajectory["span_deg"],
        "constraint_count": trajectory["constraint_count"],
        "gap_coverage_ratio": trajectory["gap_coverage_ratio"],
        "adjacent_constraints": adjacent_pairs,
        "adjacent_coverage_ratio": adjacent_coverage,
        "graph_median_abs_residual_deg": trajectory["median_abs_residual_deg"],
        "graph_max_abs_residual_deg": trajectory["max_abs_residual_deg"],
        "median_model_residual_px": statistics.median(model_errors) if model_errors else None,
        "max_model_residual_px": max(model_errors) if model_errors else None,
        "direction_sign_counts": direction_counts,
    }
    return {
        "database": str(database_path),
        "matching": database_match_stats(database_path),
        "pose": pose,
        "best_direction": selected["direction"],
        "selected_model": selected["model"],
        "selected_stats": dict(selected.get("stats", {})),
        "candidate_stats": {
            item["direction"]: dict(item.get("stats", {})) for item in candidates
        },
    }


def run_matching_ab_benchmark(project_root, run_id, colmap_path=None, overwrite=True):
    from pipeline.workflows.turntable.legacy_v13.reconstruction import estimate_turntable_translation, read_database_scene, _run_stage

    project_root = Path(project_root).resolve()
    run_root = project_root / "workspace" / "runs" / str(run_id)
    source_database = run_root / "colmap" / "database.db"
    masks_dir = run_root / "masks"
    frames_dir = run_root / "frames"
    if not source_database.exists():
        raise FileNotFoundError(f"COLMAP database not found: {source_database}")
    if not masks_dir.exists():
        raise FileNotFoundError(f"Masks directory not found: {masks_dir}")
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    paths = benchmark_paths(run_root)
    if paths["root"].exists():
        if overwrite:
            shutil.rmtree(paths["root"])
        else:
            raise FileExistsError(
                f"Diagnostics directory already exists: {paths['root']}"
            )
    paths["logs"].mkdir(parents=True, exist_ok=True)
    paths["sequential"].mkdir(parents=True, exist_ok=True)
    paths["exhaustive"].mkdir(parents=True, exist_ok=True)

    resolved_colmap = _resolve_colmap_path(colmap_path)
    camera, images = read_database_scene(source_database)
    center = estimate_turntable_translation(masks_dir, images, camera)
    tvec = tuple(float(value) for value in center["tvec"])

    source_hash_before = _sha256(source_database)
    sequential = _evaluate_database(
        "sequential",
        source_database,
        run_root,
        resolved_colmap,
        tvec,
        paths["sequential"],
        paths["logs"],
    )

    clone_database_for_exhaustive(source_database, paths["exhaustive_database"])
    _run_stage(
        resolved_colmap,
        exhaustive_matcher_args(paths["exhaustive_database"]),
        paths["logs"] / "exhaustive_matcher.log",
        run_root / "colmap",
    )
    exhaustive = _evaluate_database(
        "exhaustive",
        paths["exhaustive_database"],
        run_root,
        resolved_colmap,
        tvec,
        paths["exhaustive"],
        paths["logs"],
    )
    source_hash_after = _sha256(source_database)

    report = {
        "version": "1.3.5",
        "purpose": "turntable_matching_ab_benchmark",
        "run_id": str(run_id),
        "image_count": len(images),
        "source_database": str(source_database),
        "source_database_sha256_before": source_hash_before,
        "source_database_sha256_after": source_hash_after,
        "source_database_unchanged": source_hash_before == source_hash_after,
        "shared_sparse_untouched": str(run_root / "colmap" / "sparse" / "0"),
        "diagnostics_root": str(paths["root"]),
        "rotation_center_tvec": [float(value) for value in tvec],
        "controlled_variables": {
            "features": "existing mask-guided SIFT keypoints/descriptors",
            "pose_estimator": "turntable_constrained_essential_v134",
            "max_gap": 10,
            "max_step_rotation_deg": 20.0,
            "max_model_error_px": 3.0,
            "triangulator": "COLMAP point_triangulator",
            "changed_variable": "matcher: sequential baseline vs exhaustive",
        },
        "sequential": sequential,
        "exhaustive": exhaustive,
        "comparison": compare_matching_results(sequential, exhaustive),
    }
    paths["report"].write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report, paths["report"]


def _print_compact(report, report_path):
    compact = {
        "run_id": report["run_id"],
        "source_database_unchanged": report["source_database_unchanged"],
        "sequential": report["sequential"],
        "exhaustive": report["exhaustive"],
        "comparison": report["comparison"],
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_path}")
    print("Production database.db and shared sparse/0 were not modified.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="A/B benchmark Sequential vs Exhaustive matching for V1.3.4 constrained Turntable pose."
    )
    parser.add_argument("--run", required=True, help="Existing Videoto3D run id, e.g. hlw_04")
    parser.add_argument("--colmap", default=None, help="Optional explicit path to colmap/COLMAP.bat")
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not replace an existing diagnostics/matching_ab_v135 directory",
    )
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    report, report_path = run_matching_ab_benchmark(
        project_root,
        args.run,
        colmap_path=args.colmap,
        overwrite=not args.no_overwrite,
    )
    _print_compact(report, report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
