"""R0.3a strict A/B benchmark for multi-baseline Turntable constraints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.workflows.turntable.benchmark.metrics import (
    angle_sequence_metrics,
)
from pipeline.workflows.turntable.observations import (
    match_masked_features,
)
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
from pipeline.workflows.turntable.pose.shared_geometry import (
    directed_angle_error_deg,
    line_angle_error_deg,
    observable_transverse_orbit,
)
from pipeline.workflows.turntable.pose.synthetic_geometry import (
    camera_intrinsics_from_ground_truth,
    shared_geometry_from_ground_truth,
)


CONFIGURATIONS = {
    "A_adjacent": (1,),
    "B_gap12": (1, 2),
    "C_gap123": (1, 2, 3),
    "D_gap1235": (1, 2, 3, 5),
}


def _cache_union_matches(dataset, frames):
    cache = {}
    union_edges = edge_schedule(len(frames), CONFIGURATIONS["D_gap1235"])
    for left_index, right_index in union_edges:
        left = frames[left_index]
        right = frames[right_index]
        try:
            cache[(left_index, right_index)] = {
                "ok": True,
                "value": match_masked_features(
                    dataset / left["frame"],
                    dataset / right["frame"],
                    dataset / left["mask"],
                    dataset / right["mask"],
                ),
            }
        except RuntimeError as exc:
            cache[(left_index, right_index)] = {
                "ok": False,
                "error": str(exc),
            }
    return cache


def _cached_match_callback(cache):
    def match_pair(left_index, right_index):
        record = cache[(int(left_index), int(right_index))]
        if not record["ok"]:
            raise RuntimeError(record["error"])
        return record["value"]
    return match_pair


def _adjacent_initializer_inputs(cache, frame_count):
    raw_pairs = []
    failed = []
    for left_index in range(frame_count - 1):
        record = cache[(left_index, left_index + 1)]
        if not record["ok"]:
            failed.append(left_index)
            continue
        matched = record["value"]
        raw_pairs.append(
            {
                "left_points_px": matched["left_points_px"],
                "right_points_px": matched["right_points_px"],
            }
        )
    if failed:
        raise RuntimeError(
            "GT-free generic Essential initialization requires all "
            "adjacent pairs; failed left indices: {}".format(failed)
        )
    return raw_pairs


def _counts_by_gap_json(graph):
    result = {}
    for gap, values in graph["counts_by_gap"].items():
        result[str(int(gap))] = {
            "attempted": int(values["attempted"]),
            "accepted": int(values["accepted"]),
            "rejected": int(values["rejected"]),
        }
    return result


def _prediction_block(result):
    return {
        "axis_cv": [float(value) for value in result["axis"]],
        "transverse_orbit_direction_cv": [
            float(value)
            for value in result["transverse_orbit_direction"]
        ],
        "deltas_deg": [
            float(value)
            for value in result["deltas_deg"]
        ],
        "angles_deg": [
            float(value)
            for value in cumulative_angles_deg(result["deltas_deg"])
        ],
        "span_deg": float(result["span_deg"]),
        "converged": bool(result["converged"]),
        "termination_reason": str(result["termination_reason"]),
        "best_state_returned": bool(result["best_state_returned"]),
        "joint_objective_sampson_px": float(
            result["joint_objective_sampson_px"]
        ),
        "iteration_count": int(result["iteration_count"]),
        "solver_mode": str(
            result.get("solver_mode", "unknown")
        ),
        "accepted_joint_objective_history_px": [
            float(value)
            for value in result[
                "accepted_joint_objective_history_px"
            ]
        ],
        "history": result["history"],
    }


def _promotion_ok(metrics, predicted, baseline_metrics):
    return bool(
        metrics["axis_line_error_deg"] < 1.0
        and metrics["transverse_orbit_line_error_deg"] < 1.0
        and metrics["increment_mae_deg"] < 0.15
        and metrics["span_error_deg"] < 2.0
        and metrics["angle_mae_deg"] < 2.0
        and metrics["monotonicity_violations"] == 0
        and predicted["best_state_returned"] is True
        and metrics["span_error_deg"] < baseline_metrics["span_error_deg"]
        and metrics["angle_mae_deg"] < baseline_metrics["angle_mae_deg"]
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Turntable R0.3a multi-baseline A/B benchmark "
            "with GT-free optimization."
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-points", type=int, default=160)
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--keep-ratio", type=float, default=0.70)
    parser.add_argument(
        "--geometry-pairs",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--geometry-coarse-step",
        type=float,
        default=30.0,
    )
    parser.add_argument(
        "--geometry-top-k",
        type=int,
        default=8,
    )
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset).resolve()
    gt_path = dataset / "ground_truth.json"
    if not gt_path.exists():
        raise SystemExit("ground_truth.json missing: {}".format(gt_path))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    frames = gt["frames"]

    # Calibration is a permitted synthetic benchmark input.
    intrinsics = camera_intrinsics_from_ground_truth(gt["camera"])

    cache_started = time.perf_counter()
    cache = _cache_union_matches(dataset, frames)
    cache_runtime = time.perf_counter() - cache_started

    raw_adjacent = _adjacent_initializer_inputs(
        cache,
        len(frames),
    )
    initialization = initialize_from_generic_essential(
        raw_adjacent,
        intrinsics,
        min_angle_deg=0.25,
        max_angle_deg=20.0,
    )

    match_pair = _cached_match_callback(cache)
    predictions = {}
    graph_metadata = {}
    runtimes = {}

    # All A/B/C/D runs use the exact same GT-free initial state and cache.
    for name, gaps in CONFIGURATIONS.items():
        graph = build_observation_graph(
            frame_count=len(frames),
            gaps=gaps,
            match_pair=match_pair,
            min_correspondences=8,
        )
        prepared_edges = prepare_graph_edges(
            graph["accepted_edges"],
            intrinsics,
            max_points=args.max_points,
        )

        started = time.perf_counter()
        result = alternating_multibaseline_refinement(
            prepared_edges,
            initialization["axis"].copy(),
            initialization[
                "transverse_orbit_direction"
            ].copy(),
            initialization["initial_deltas_deg"].copy(),
            geometry_pair_count=args.geometry_pairs,
            max_iterations=args.iterations,
            keep_ratio=args.keep_ratio,
            geometry_coarse_step_deg=args.geometry_coarse_step,
            geometry_top_k=args.geometry_top_k,
        )
        runtimes[name] = float(time.perf_counter() - started)
        predictions[name] = _prediction_block(result)
        graph_metadata[name] = {
            "enabled_gaps": [int(gap) for gap in gaps],
            "attempted_edge_count": int(
                graph["attempted_edge_count"]
            ),
            "accepted_edge_count": int(
                graph["accepted_edge_count"]
            ),
            "rejected_edge_count": int(
                graph["rejected_edge_count"]
            ),
            "counts_by_gap": _counts_by_gap_json(graph),
        }

    # Evaluation-only GT access starts here.
    ground_truth_angles = [
        float(frame["angle_deg"])
        for frame in frames
    ]
    gt_geometry = shared_geometry_from_ground_truth(gt)
    gt_axis = gt_geometry["axis_cv"]
    gt_transverse = observable_transverse_orbit(
        gt_axis,
        gt_geometry["orbit_vector_cv"],
    )

    evaluated = {}
    for name, prediction in predictions.items():
        angle_metrics = angle_sequence_metrics(
            prediction["angles_deg"],
            ground_truth_angles,
        )
        evaluated[name] = {
            "axis_line_error_deg": float(
                line_angle_error_deg(
                    prediction["axis_cv"],
                    gt_axis,
                )
            ),
            "axis_directed_error_deg": float(
                directed_angle_error_deg(
                    prediction["axis_cv"],
                    gt_axis,
                )
            ),
            "transverse_orbit_line_error_deg": float(
                line_angle_error_deg(
                    prediction[
                        "transverse_orbit_direction_cv"
                    ],
                    gt_transverse,
                )
            ),
            "angle_mae_deg": float(
                angle_metrics["angle_mae_deg"]
            ),
            "increment_mae_deg": float(
                angle_metrics["increment_mae_deg"]
            ),
            "span_error_deg": float(
                angle_metrics["span_error_deg"]
            ),
            "monotonicity_violations": int(
                angle_metrics["monotonicity_violations"]
            ),
        }

    baseline_metrics = evaluated["A_adjacent"]
    promotion_candidates = [
        name
        for name in ("B_gap12", "C_gap123", "D_gap1235")
        if _promotion_ok(
            evaluated[name],
            predictions[name],
            baseline_metrics,
        )
    ]

    best_span = min(
        evaluated,
        key=lambda name: evaluated[name]["span_error_deg"],
    )
    best_angle = min(
        evaluated,
        key=lambda name: evaluated[name]["angle_mae_deg"],
    )

    configurations = {}
    for name in CONFIGURATIONS:
        configurations[name] = {
            **graph_metadata[name],
            "runtime_sec": runtimes[name],
            "predicted": predictions[name],
            "metrics": evaluated[name],
        }

    report = {
        "schema_version": 1,
        "stage": "turntable_r03a_multibaseline_ab",
        "estimator_inputs": {
            "ground_truth_axis_used": False,
            "ground_truth_orbit_used": False,
            "ground_truth_angles_used": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
            "one_direction_monotonic_prior": True,
            "camera_intrinsics_source":
                "synthetic_ground_truth_calibration_only",
        },
        "dataset": str(dataset),
        "feature_cache_runtime_sec": float(cache_runtime),
        "initialization": {
            "method": initialization["method"],
            "valid_pair_count": int(
                initialization["valid_pair_count"]
            ),
            "fallback_pair_count": int(
                initialization["fallback_pair_count"]
            ),
            "initial_span_deg": float(
                np.sum(
                    initialization[
                        "initial_deltas_deg"
                    ]
                )
            ),
            "forced_360_degree_span": False,
        },
        "configurations": configurations,
        "comparison": {
            "baseline": "A_adjacent",
            "best_span_error_configuration": best_span,
            "best_angle_mae_configuration": best_angle,
            "promotion_pass": bool(promotion_candidates),
            "promotion_candidates": promotion_candidates,
        },
        "evaluation_ground_truth": {
            "axis_cv": [float(v) for v in gt_axis],
            "transverse_orbit_direction_cv": [
                float(v) for v in gt_transverse
            ],
            "span_deg": float(
                ground_truth_angles[-1]
                - ground_truth_angles[0]
            ),
        },
    }

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (
            dataset.parent.parent
            / "r03a"
            / dataset.name
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "r03a_ab_report.json"
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    summary = {
        name: {
            "gaps": configurations[name]["enabled_gaps"],
            "edges": configurations[name]["accepted_edge_count"],
            "span_error_deg":
                configurations[name]["metrics"]["span_error_deg"],
            "angle_mae_deg":
                configurations[name]["metrics"]["angle_mae_deg"],
            "increment_mae_deg":
                configurations[name]["metrics"]["increment_mae_deg"],
            "axis_error_deg":
                configurations[name]["metrics"]["axis_line_error_deg"],
            "orbit_error_deg":
                configurations[name]["metrics"][
                    "transverse_orbit_line_error_deg"
                ],
            "runtime_sec": configurations[name]["runtime_sec"],
        }
        for name in CONFIGURATIONS
    }
    print(json.dumps(summary, indent=2))
    print(
        json.dumps(
            report["comparison"],
            indent=2,
        )
    )
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
