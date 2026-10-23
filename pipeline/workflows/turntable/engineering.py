"""Run-local Turntable engineering stages.

The module deliberately owns every path under workspace/runs/<run_id>.
External tools are executable providers only.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import struct
import subprocess
from pathlib import Path

import numpy as np

from pipeline.capture_mode import normalize_capture_mode
from pipeline.workflows.turntable.observations import match_masked_features
from pipeline.workflows.turntable.observations.graph import (
    build_observation_graph,
    edge_schedule,
)
from pipeline.workflows.turntable.pose.initialization import (
    initialize_from_generic_essential,
)
from pipeline.workflows.turntable.pose.multibaseline import (
    alternating_multibaseline_refinement,
    cumulative_angles_deg,
    prepare_graph_edges,
)
from pipeline.workflows.turntable.pose.multi_hypothesis import (
    generate_pair_hypotheses,
)
from pipeline.workflows.turntable.pose.global_orbit import (
    measurements_from_r03c,
    solve_global_orbit,
)
from pipeline.workflows.turntable.geometry.known_pose_colmap import (
    feature_extractor_args,
    point_triangulator_args,
    sequential_matcher_args,
    write_known_pose_text_model,
)
from pipeline.workflows.turntable.legacy_v13.reconstruction import (
    run_turntable_reconstruction,
)

UNION_GAPS = (1, 2, 3, 5)
PRIMARY_GAPS = (2, 3, 5)


def assert_run_local_path(run_root, path):
    run_root = Path(run_root).resolve()
    path = Path(path).resolve()
    try:
        path.relative_to(run_root)
    except ValueError:
        raise RuntimeError(
            "Refusing to write outside Run workspace: {}".format(path)
        )
    return path


def _atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(str(tmp), str(path))


def _manifest(run_root):
    path = Path(run_root) / "run.json"
    if not path.exists():
        raise FileNotFoundError("run.json missing: {}".format(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _require_turntable(run_root):
    manifest = _manifest(run_root)
    mode = normalize_capture_mode(manifest.get("capture_mode"))
    if mode != "turntable":
        raise RuntimeError(
            "Turntable stage requires capture_mode=turntable; Run uses {}."
            .format(mode)
        )
    return manifest


def update_turntable_stage(run_root, stage, status, **fields):
    run_root = Path(run_root).resolve()
    assert_run_local_path(run_root, run_root / "run.json")
    manifest = _manifest(run_root)
    section = manifest.setdefault("turntable", {})
    entry = dict(section.get(stage, {}))
    entry.update(fields)
    entry["status"] = str(status)
    section[stage] = entry
    _atomic_json(run_root / "run.json", manifest)
    return entry


def turntable_stage_ready(run_root, stage):
    try:
        manifest = _manifest(run_root)
    except FileNotFoundError:
        return False
    return (
        manifest.get("turntable", {})
        .get(stage, {})
        .get("status") == "ready"
    )


def _remove(path):
    path = Path(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def invalidate_after_turntable_stage(run_root, stage):
    run_root = Path(run_root).resolve()
    order = ("anchor", "pairs", "orbit", "triangulate")
    if stage not in order:
        raise ValueError("Unknown Turntable stage: {}".format(stage))
    manifest = _manifest(run_root)
    section = manifest.setdefault("turntable", {})
    index = order.index(stage)
    for downstream in order[index + 1:]:
        section.pop(downstream, None)

    if index <= order.index("pairs"):
        _remove(run_root / "turntable" / "pairs.json")
    if index <= order.index("orbit"):
        _remove(run_root / "turntable" / "orbit.json")
    if index <= order.index("triangulate"):
        _remove(run_root / "colmap")
        for name in ("mesh", "output"):
            _remove(run_root / name)
        routes = manifest.get("routes", {})
        routes.pop("mesh", None)
        manifest.get("shared", {}).pop("sparse", None)

    _atomic_json(run_root / "run.json", manifest)


def invalidate_all_turntable(run_root):
    run_root = Path(run_root).resolve()
    _remove(run_root / "turntable")
    manifest = _manifest(run_root)
    manifest.pop("turntable", None)
    _atomic_json(run_root / "run.json", manifest)


def _frame_paths(run_root):
    frames_dir = Path(run_root) / "frames"
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        frames = sorted(frames_dir.glob("*.jpg"))
    if not frames:
        frames = sorted(frames_dir.glob("*.png"))
    if len(frames) < 3:
        raise RuntimeError("Turntable requires at least 3 frames.")
    return frames


def _mask_for_frame(run_root, frame):
    masks = Path(run_root) / "masks"
    candidates = (
        masks / (frame.name + ".png"),
        masks / (frame.stem + ".png"),
        masks / frame.name,
    )
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("Mask missing for frame {}".format(frame.name))


def _camera_intrinsics_from_database(database_path):
    con = sqlite3.connect(str(database_path))
    try:
        row = con.execute(
            "SELECT model, width, height, params FROM cameras "
            "ORDER BY camera_id LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise RuntimeError("No camera found in bootstrap COLMAP database.")
    model, width, height, blob = row
    params = np.frombuffer(blob, dtype=np.float64).copy()
    model = int(model)

    # COLMAP camera model IDs. Only the first intrinsic block is needed here.
    if model in (0, 2, 3, 8, 9):  # SIMPLE_* families
        if len(params) < 3:
            raise RuntimeError("Unexpected SIMPLE camera parameter count.")
        fx = fy = float(params[0])
        cx, cy = float(params[1]), float(params[2])
    else:  # PINHOLE / OPENCV / fisheye families
        if len(params) < 4:
            raise RuntimeError("Unexpected camera parameter count.")
        fx, fy, cx, cy = [float(v) for v in params[:4]]

    k = np.asarray(
        [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    return {
        "model_id": model,
        "width": int(width),
        "height": int(height),
        "intrinsics_px": k,
    }


def _cache_matches(run_root, frames):
    cache = {}
    for left_index, right_index in edge_schedule(len(frames), UNION_GAPS):
        left = frames[left_index]
        right = frames[right_index]
        try:
            value = match_masked_features(
                left,
                right,
                _mask_for_frame(run_root, left),
                _mask_for_frame(run_root, right),
            )
            cache[(left_index, right_index)] = {
                "ok": True,
                "value": value,
            }
        except RuntimeError as exc:
            cache[(left_index, right_index)] = {
                "ok": False,
                "error": str(exc),
            }
    return cache


def _save_match_cache(run_root, cache):
    root = Path(run_root) / "turntable" / "observations"
    root.mkdir(parents=True, exist_ok=True)
    arrays = {}
    metadata = []
    for index, ((left, right), record) in enumerate(sorted(cache.items())):
        item = {
            "index": index,
            "left_index": int(left),
            "right_index": int(right),
            "gap": int(right - left),
            "ok": bool(record["ok"]),
        }
        if record["ok"]:
            matched = record["value"]
            arrays["left_{}".format(index)] = np.asarray(
                matched["left_points_px"], dtype=np.float64
            )
            arrays["right_{}".format(index)] = np.asarray(
                matched["right_points_px"], dtype=np.float64
            )
            item["raw_match_count"] = int(matched.get("match_count", 0))
            item["feature_method"] = str(matched.get("method", "UNKNOWN"))
        else:
            item["error"] = str(record["error"])
        metadata.append(item)
    np.savez_compressed(root / "graph.npz", **arrays)
    _atomic_json(root / "graph.json", {"edges": metadata})
    return root


def _load_match_cache(run_root):
    root = Path(run_root) / "turntable" / "observations"
    meta_path = root / "graph.json"
    npz_path = root / "graph.npz"
    if not meta_path.exists() or not npz_path.exists():
        raise RuntimeError("Turntable observations missing. Run anchor first.")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))["edges"]
    data = np.load(npz_path)
    cache = {}
    for item in metadata:
        key = (int(item["left_index"]), int(item["right_index"]))
        if item["ok"]:
            idx = int(item["index"])
            cache[key] = {
                "ok": True,
                "value": {
                    "left_points_px": np.asarray(data["left_{}".format(idx)]),
                    "right_points_px": np.asarray(data["right_{}".format(idx)]),
                    "match_count": int(item.get("raw_match_count", 0)),
                    "method": item.get("feature_method", "UNKNOWN"),
                },
            }
        else:
            cache[key] = {"ok": False, "error": item.get("error", "")}
    return cache


def _cached_callback(cache):
    def match_pair(left_index, right_index):
        record = cache[(int(left_index), int(right_index))]
        if not record["ok"]:
            raise RuntimeError(record["error"])
        return record["value"]
    return match_pair


def _adjacent_initializer_inputs(cache, frame_count):
    raw = []
    failed = []
    for left in range(frame_count - 1):
        record = cache[(left, left + 1)]
        if not record["ok"]:
            failed.append(left)
            continue
        value = record["value"]
        raw.append({
            "left_points_px": value["left_points_px"],
            "right_points_px": value["right_points_px"],
        })
    if failed:
        raise RuntimeError(
            "Turntable adjacent initialization failed at: {}".format(failed)
        )
    return raw


def _anchor_payload(result, calibration, frame_count):
    return {
        "schema_version": 1,
        "stage": "turntable_anchor",
        "estimator_inputs": {
            "ground_truth_pose_used": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
            "intrinsics_source": calibration["source"],
        },
        "frame_count": int(frame_count),
        "calibration": {
            "width": int(calibration["width"]),
            "height": int(calibration["height"]),
            "intrinsics_px": calibration["intrinsics_px"].tolist(),
            "source": calibration["source"],
        },
        "axis_cv": [float(v) for v in result["axis"]],
        "transverse_orbit_direction_cv": [
            float(v) for v in result["transverse_orbit_direction"]
        ],
        "initial_deltas_deg": [float(v) for v in result["deltas_deg"]],
        "initial_angles_deg": [
            float(v) for v in cumulative_angles_deg(result["deltas_deg"])
        ],
        "initial_span_deg": float(result["span_deg"]),
        "objective_px": float(result["joint_objective_sampson_px"]),
        "converged": bool(result["converged"]),
        "termination_reason": str(result["termination_reason"]),
    }


def run_anchor_stage(colmap_path, run_root, overwrite=True):
    run_root = Path(run_root).resolve()
    _require_turntable(run_root)
    frames = _frame_paths(run_root)

    invalidate_after_turntable_stage(run_root, "anchor")
    turntable_root = run_root / "turntable"
    turntable_root.mkdir(parents=True, exist_ok=True)
    logs_dir = run_root / "logs" / "turntable" / "bootstrap"
    bootstrap_colmap = turntable_root / "bootstrap_colmap"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Engineering bootstrap: obtain real-video intrinsics from frozen V1.3.
    bootstrap = run_turntable_reconstruction(
        colmap_path=colmap_path,
        frames_dir=run_root / "frames",
        masks_dir=run_root / "masks",
        colmap_dir=bootstrap_colmap,
        logs_dir=logs_dir,
        overwrite=True,
    )
    camera = _camera_intrinsics_from_database(bootstrap["database"])
    calibration = {
        **camera,
        "source": "v13_bootstrap_colmap_intrinsics_only",
    }
    _atomic_json(
        turntable_root / "calibration.json",
        {
            "source": calibration["source"],
            "model_id": calibration["model_id"],
            "width": calibration["width"],
            "height": calibration["height"],
            "intrinsics_px": calibration["intrinsics_px"].tolist(),
        },
    )

    cache = _cache_matches(run_root, frames)
    _save_match_cache(run_root, cache)
    raw_adjacent = _adjacent_initializer_inputs(cache, len(frames))
    k = calibration["intrinsics_px"]

    initialization = initialize_from_generic_essential(
        raw_adjacent,
        k,
        min_angle_deg=0.25,
        max_angle_deg=20.0,
    )
    graph = build_observation_graph(
        frame_count=len(frames),
        gaps=(1, 2, 3),
        match_pair=_cached_callback(cache),
        min_correspondences=8,
    )
    edges = prepare_graph_edges(
        graph["accepted_edges"],
        k,
        max_points=160,
    )
    result = alternating_multibaseline_refinement(
        edges,
        initialization["axis"],
        initialization["transverse_orbit_direction"],
        initialization["initial_deltas_deg"],
        geometry_pair_count=12,
        max_iterations=12,
        keep_ratio=0.70,
        geometry_coarse_step_deg=30.0,
        geometry_top_k=8,
    )
    payload = _anchor_payload(result, calibration, len(frames))
    anchor_path = turntable_root / "anchor.json"
    _atomic_json(anchor_path, payload)
    update_turntable_stage(
        run_root,
        "anchor",
        "ready",
        path="turntable/anchor.json",
        observation_graph="turntable/observations/graph.json",
        span_deg=payload["initial_span_deg"],
        frame_count=len(frames),
    )
    return payload


def run_pairs_stage(run_root):
    run_root = Path(run_root).resolve()
    _require_turntable(run_root)
    invalidate_after_turntable_stage(run_root, "pairs")

    anchor_path = run_root / "turntable" / "anchor.json"
    if not anchor_path.exists():
        raise RuntimeError("Turntable anchor missing. Run anchor first.")
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    cache = _load_match_cache(run_root)
    frame_count = int(anchor["frame_count"])
    k = np.asarray(anchor["calibration"]["intrinsics_px"], dtype=np.float64)

    graph = build_observation_graph(
        frame_count=frame_count,
        gaps=PRIMARY_GAPS,
        match_pair=_cached_callback(cache),
        min_correspondences=8,
    )
    edges = prepare_graph_edges(
        graph["accepted_edges"],
        k,
        max_points=160,
    )
    axis = np.asarray(anchor["axis_cv"], dtype=np.float64)
    transverse = np.asarray(
        anchor["transverse_orbit_direction_cv"], dtype=np.float64
    )
    hypotheses = []
    for edge in edges:
        hypotheses.append(
            generate_pair_hypotheses(
                edge,
                axis,
                transverse,
                min_angle_deg=0.25,
                max_angle_deg=60.0,
                coarse_step_deg=0.5,
                refine_step_deg=0.05,
                top_k=3,
                min_separation_deg=0.5,
                keep_ratio=0.70,
            )
        )
    payload = {
        "schema_version": 1,
        "stage": "turntable_pairs",
        "estimator_inputs": {
            "ground_truth_angles_used": False,
            "ground_truth_span_used": False,
            "anchor_trajectory_angles_used_for_pair_search": False,
        },
        "frame_count": frame_count,
        "hypotheses": hypotheses,
        "accepted_edge_count": len(hypotheses),
        "rejected_edge_count": len(graph.get("rejected_edges", [])),
    }
    _atomic_json(run_root / "turntable" / "pairs.json", payload)
    update_turntable_stage(
        run_root,
        "pairs",
        "ready",
        path="turntable/pairs.json",
        edge_count=len(hypotheses),
    )
    return payload


def run_orbit_stage(run_root):
    run_root = Path(run_root).resolve()
    _require_turntable(run_root)
    invalidate_after_turntable_stage(run_root, "orbit")
    pairs_path = run_root / "turntable" / "pairs.json"
    anchor_path = run_root / "turntable" / "anchor.json"
    if not pairs_path.exists() or not anchor_path.exists():
        raise RuntimeError("Turntable pairs/anchor missing.")
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))

    measurement_info = measurements_from_r03c(
        {"hypotheses": pairs["hypotheses"]},
        include_gap5=True,
    )
    solved = solve_global_orbit(
        frame_count=int(pairs["frame_count"]),
        measurements=measurement_info["measurements"],
        irls_iterations=8,
        huber_delta_deg=0.35,
    )
    payload = {
        "schema_version": 1,
        "stage": "turntable_global_orbit",
        "estimator_inputs": {
            "ground_truth_angles_used": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
        },
        "shared_geometry": {
            "axis_cv": anchor["axis_cv"],
            "transverse_orbit_direction_cv":
                anchor["transverse_orbit_direction_cv"],
        },
        "measurement_gate": {
            "accepted_count": len(measurement_info["measurements"]),
            "rejected_count": len(measurement_info["rejected"]),
            "gap5_residual_threshold_px":
                measurement_info["gap5_residual_threshold_px"],
            "rejected": measurement_info["rejected"],
        },
        "global_orbit": solved,
    }
    _atomic_json(run_root / "turntable" / "orbit.json", payload)
    update_turntable_stage(
        run_root,
        "orbit",
        "ready",
        path="turntable/orbit.json",
        span_deg=solved["span_deg"],
        monotonicity_violations=solved["monotonicity_violations"],
    )
    return payload


def _colmap_command(colmap_path, args):
    path = Path(colmap_path)
    if path.suffix.lower() in (".bat", ".cmd"):
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d", "/c", str(path),
        ] + list(args)
    return [str(path)] + list(args)


def _run_colmap(colmap_path, args, cwd, log_path):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as stream:
        result = subprocess.run(
            _colmap_command(colmap_path, args),
            cwd=str(cwd),
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(
            "COLMAP command failed ({}). See {}".format(
                args[0], log_path
            )
        )


def _stage_feature_masks(run_root, frames):
    output = Path(run_root) / "turntable" / "feature_masks"
    _remove(output)
    output.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        source = _mask_for_frame(run_root, frame)
        target = output / (frame.name + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return output


def _binary_count(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size < 8:
        return None
    with path.open("rb") as stream:
        return int(struct.unpack("<Q", stream.read(8))[0])


def run_triangulate_stage(colmap_path, run_root, overwrite=True):
    run_root = Path(run_root).resolve()
    _require_turntable(run_root)
    invalidate_after_turntable_stage(run_root, "triangulate")

    orbit_path = run_root / "turntable" / "orbit.json"
    anchor_path = run_root / "turntable" / "anchor.json"
    if not orbit_path.exists() or not anchor_path.exists():
        raise RuntimeError("Turntable orbit/anchor missing.")
    orbit = json.loads(orbit_path.read_text(encoding="utf-8"))
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    frames = _frame_paths(run_root)

    colmap_root = run_root / "colmap"
    _remove(colmap_root)
    colmap_root.mkdir(parents=True, exist_ok=True)
    logs = run_root / "logs" / "turntable"
    logs.mkdir(parents=True, exist_ok=True)
    database = colmap_root / "database.db"
    known_pose = colmap_root / "known_pose"
    sparse = colmap_root / "sparse" / "0"
    sparse.mkdir(parents=True, exist_ok=True)

    image_list = run_root / "turntable" / "image_list.txt"
    image_names = [frame.name for frame in frames]
    image_list.write_text("\n".join(image_names) + "\n", encoding="utf-8")
    mask_root = _stage_feature_masks(run_root, frames)

    k = np.asarray(anchor["calibration"]["intrinsics_px"], dtype=np.float64)
    feature_args = feature_extractor_args(
        database_path=database,
        image_path=run_root / "frames",
        image_list_path=image_list,
        intrinsics=k,
        mask_path=mask_root,
    )
    _run_colmap(
        colmap_path,
        feature_args,
        run_root,
        logs / "triangulate_01_feature_extractor.log",
    )
    _run_colmap(
        colmap_path,
        sequential_matcher_args(database, overlap=8),
        run_root,
        logs / "triangulate_02_sequential_matcher.log",
    )

    angles = orbit["global_orbit"]["angles_deg"]
    write_known_pose_text_model(
        database_path=database,
        output_dir=known_pose,
        image_names=image_names,
        angles_deg=angles,
        axis=orbit["shared_geometry"]["axis_cv"],
        transverse_direction=orbit["shared_geometry"][
            "transverse_orbit_direction_cv"
        ],
        intrinsics=k,
        width=int(anchor["calibration"]["width"]),
        height=int(anchor["calibration"]["height"]),
    )
    _run_colmap(
        colmap_path,
        point_triangulator_args(
            database_path=database,
            image_path=run_root / "frames",
            input_path=known_pose,
            output_path=sparse,
        ),
        run_root,
        logs / "triangulate_03_point_triangulator.log",
    )

    image_count = _binary_count(sparse / "images.bin") or len(frames)
    point_count = _binary_count(sparse / "points3D.bin")
    update_turntable_stage(
        run_root,
        "triangulate",
        "ready",
        model="colmap/sparse/0",
        database="colmap/database.db",
        registered_images=image_count,
        points3D=point_count,
    )
    return {
        "frame_count": len(frames),
        "database": database,
        "model": sparse,
        "stats": {
            "registered_images": image_count,
            "points3D": point_count,
            "mean_track_length": None,
            "mean_reprojection_error": None,
        },
    }


def run_sparse_engineering(colmap_path, run_root):
    run_anchor_stage(colmap_path, run_root, overwrite=True)
    run_pairs_stage(run_root)
    run_orbit_stage(run_root)
    return run_triangulate_stage(
        colmap_path, run_root, overwrite=True
    )
