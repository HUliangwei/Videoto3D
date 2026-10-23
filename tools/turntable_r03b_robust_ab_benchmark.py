"""R0.3b robust multi-baseline A/B benchmark for Turntable research."""
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

from pipeline.workflows.turntable.benchmark.metrics import angle_sequence_metrics
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
from pipeline.workflows.turntable.pose.robust_multibaseline import (
    alternating_robust_multibaseline_refinement,
    diagnose_graph_edges,
    gate_long_baseline_edges,
    robust_graph_weights,
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


UNION_GAPS = (1, 2, 3, 5)


def _cache_union_matches(dataset, frames):
    cache = {}
    for left_index, right_index in edge_schedule(len(frames), UNION_GAPS):
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


def _graph_for_gaps(frame_count, gaps, match_pair):
    return build_observation_graph(
        frame_count=frame_count,
        gaps=gaps,
        match_pair=match_pair,
        min_correspondences=8,
    )


def _prediction_block(result):
    return {
        "axis_cv": [float(value) for value in result["axis"]],
        "transverse_orbit_direction_cv": [
            float(value)
            for value in result["transverse_orbit_direction"]
        ],
        "deltas_deg": [float(value) for value in result["deltas_deg"]],
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
        "solver_mode": str(result.get("solver_mode", "unknown")),
        "accepted_joint_objective_history_px": [
            float(value)
            for value in result["accepted_joint_objective_history_px"]
        ],
        "history": result["history"],
    }


def _run_r03a(
    prepared_edges,
    initial_axis,
    initial_transverse,
    initial_deltas,
    args,
):
    started = time.perf_counter()
    result = alternating_multibaseline_refinement(
        prepared_edges,
        initial_axis.copy(),
        initial_transverse.copy(),
        initial_deltas.copy(),
        geometry_pair_count=args.geometry_pairs,
        max_iterations=args.iterations,
        keep_ratio=args.keep_ratio,
        geometry_coarse_step_deg=args.geometry_coarse_step,
        geometry_top_k=args.geometry_top_k,
    )
    return result, float(time.perf_counter() - started)


def _run_robust(
    prepared_edges,
    anchor,
    weights,
    args,
    regularity_weight_px=0.0,
):
    started = time.perf_counter()
    result = alternating_robust_multibaseline_refinement(
        prepared_edges,
        anchor["axis"].copy(),
        anchor["transverse_orbit_direction"].copy(),
        anchor["deltas_deg"].copy(),
        weights,
        geometry_pair_count=args.geometry_pairs,
        max_iterations=args.iterations,
        keep_ratio=args.keep_ratio,
        geometry_coarse_step_deg=args.geometry_coarse_step,
        geometry_top_k=args.geometry_top_k,
        regularity_weight_px=float(regularity_weight_px),
    )
    return result, float(time.perf_counter() - started)


def _counts_by_gap(edges):
    result = {}
    for edge in edges:
        gap = str(int(edge["gap"]))
        result[gap] = int(result.get(gap, 0) + 1)
    return result


def _promotion_ok(metrics, predicted, anchor_metrics):
    history = predicted["accepted_joint_objective_history_px"]
    monotonic_objective = all(
        right <= left + 1e-12
        for left, right in zip(history[:-1], history[1:])
    )
    return bool(
        metrics["span_error_deg"] < anchor_metrics["span_error_deg"]
        and metrics["angle_mae_deg"]
        <= anchor_metrics["angle_mae_deg"] + 0.10
        and metrics["axis_line_error_deg"] < 1.0
        and metrics["transverse_orbit_line_error_deg"] < 1.0
        and metrics["increment_mae_deg"] < 0.15
        and metrics["span_error_deg"] < 2.0
        and metrics["angle_mae_deg"] < 2.0
        and metrics["monotonicity_violations"] == 0
        and predicted["best_state_returned"] is True
        and monotonic_objective
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Turntable R0.3b robust gap5 weighting/gating A/B benchmark."
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-points", type=int, default=160)
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--keep-ratio", type=float, default=0.70)
    parser.add_argument("--geometry-pairs", type=int, default=12)
    parser.add_argument("--geometry-coarse-step", type=float, default=30.0)
    parser.add_argument("--geometry-top-k", type=int, default=8)
    parser.add_argument("--diagnostic-window", type=float, default=4.0)
    parser.add_argument("--diagnostic-step", type=float, default=0.10)
    parser.add_argument(
        "--regularity-weight",
        type=float,
        default=0.0,
        help=(
            "Optional weak second-difference regularity ablation. "
            "0 disables the G configuration."
        ),
    )
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset).resolve()
    gt_path = dataset / "ground_truth.json"
    if not gt_path.exists():
        raise SystemExit("ground_truth.json missing: {}".format(gt_path))

    payload = json.loads(gt_path.read_text(encoding="utf-8"))
    frames = payload["frames"]
    intrinsics = camera_intrinsics_from_ground_truth(payload["camera"])

    cache_started = time.perf_counter()
    cache = _cache_union_matches(dataset, frames)
    feature_cache_runtime = float(time.perf_counter() - cache_started)
    match_pair = _cached_match_callback(cache)

    raw_adjacent = _adjacent_initializer_inputs(cache, len(frames))
    initialization = initialize_from_generic_essential(
        raw_adjacent,
        intrinsics,
        min_angle_deg=0.25,
        max_angle_deg=20.0,
    )

    # A: frozen adjacent-only behavior via R0.3a delegate path.
    graph_a = _graph_for_gaps(len(frames), (1,), match_pair)
    edges_a = prepare_graph_edges(
        graph_a["accepted_edges"],
        intrinsics,
        max_points=args.max_points,
    )
    result_a, runtime_a = _run_r03a(
        edges_a,
        initialization["axis"],
        initialization["transverse_orbit_direction"],
        initialization["initial_deltas_deg"],
        args,
    )

    # B: reliable gap {1,2,3} R0.3a anchor.
    graph_b = _graph_for_gaps(len(frames), (1, 2, 3), match_pair)
    edges_b = prepare_graph_edges(
        graph_b["accepted_edges"],
        intrinsics,
        max_points=args.max_points,
    )
    result_b, runtime_b = _run_r03a(
        edges_b,
        initialization["axis"],
        initialization["transverse_orbit_direction"],
        initialization["initial_deltas_deg"],
        args,
    )

    # Candidate full graph for all gap5 treatment ablations.
    graph_full = _graph_for_gaps(len(frames), UNION_GAPS, match_pair)
    edges_full = prepare_graph_edges(
        graph_full["accepted_edges"],
        intrinsics,
        max_points=args.max_points,
    )

    diagnostics = diagnose_graph_edges(
        edges_full,
        result_b["axis"],
        result_b["transverse_orbit_direction"],
        result_b["deltas_deg"],
        keep_ratio=args.keep_ratio,
        search_window_deg=args.diagnostic_window,
        search_step_deg=args.diagnostic_step,
    )
    gated = gate_long_baseline_edges(
        edges_full,
        diagnostics,
        trusted_max_gap=3,
    )

    variants = {
        "A_adjacent": {
            "result": result_a,
            "runtime_sec": runtime_a,
            "edges": edges_a,
            "weighting": "r02b21_adjacent_baseline",
            "gating": "none",
        },
        "B_gap123_anchor": {
            "result": result_b,
            "runtime_sec": runtime_b,
            "edges": edges_b,
            "weighting": "r03a_equal_family",
            "gating": "none",
        },
    }

    # C/D/E use raw full graph and differ only by fixed weighting.
    for name, strategy in (
        ("C_gap1235_equal_family_raw", "equal_family"),
        ("D_gap1235_equal_edge", "equal_edge"),
        ("E_gap1235_sqrt_family", "sqrt_family"),
    ):
        weights = robust_graph_weights(edges_full, strategy)
        result, runtime = _run_robust(
            edges_full,
            result_b,
            weights,
            args,
        )
        variants[name] = {
            "result": result,
            "runtime_sec": runtime,
            "edges": edges_full,
            "weighting": strategy,
            "gating": "none",
            "weights": [float(value) for value in weights],
        }

    # F: robust gating + confidence-weighted fixed objective.
    gated_edges = gated["accepted_edges"]
    gated_diagnostics = gated["accepted_diagnostics"]
    gated_weights = robust_graph_weights(
        gated_edges,
        "confidence_weighted",
        diagnostics=gated_diagnostics,
    )
    result_f, runtime_f = _run_robust(
        gated_edges,
        result_b,
        gated_weights,
        args,
    )
    variants["F_gap1235_gated_confidence"] = {
        "result": result_f,
        "runtime_sec": runtime_f,
        "edges": gated_edges,
        "weighting": "confidence_weighted",
        "gating": "trusted_gap123_mad_gate",
        "weights": [float(value) for value in gated_weights],
    }

    if float(args.regularity_weight) > 0.0:
        result_g, runtime_g = _run_robust(
            gated_edges,
            result_b,
            gated_weights,
            args,
            regularity_weight_px=float(args.regularity_weight),
        )
        variants["G_gap1235_gated_confidence_regularized"] = {
            "result": result_g,
            "runtime_sec": runtime_g,
            "edges": gated_edges,
            "weighting": "confidence_weighted",
            "gating": "trusted_gap123_mad_gate",
            "regularity_weight_px": float(args.regularity_weight),
            "weights": [float(value) for value in gated_weights],
        }

    # Evaluation-only GT access begins after every prediction is complete.
    gt_angles = [
        float(frame["angle_deg"])
        for frame in frames
    ]
    gt_geometry = shared_geometry_from_ground_truth(payload)
    gt_axis = gt_geometry["axis_cv"]
    gt_transverse = observable_transverse_orbit(
        gt_axis,
        gt_geometry["orbit_vector_cv"],
    )

    configurations = {}
    for name, record in variants.items():
        predicted = _prediction_block(record["result"])
        angle_metrics = angle_sequence_metrics(
            predicted["angles_deg"],
            gt_angles,
        )
        metrics = {
            "axis_line_error_deg": float(
                line_angle_error_deg(predicted["axis_cv"], gt_axis)
            ),
            "axis_directed_error_deg": float(
                directed_angle_error_deg(predicted["axis_cv"], gt_axis)
            ),
            "transverse_orbit_line_error_deg": float(
                line_angle_error_deg(
                    predicted["transverse_orbit_direction_cv"],
                    gt_transverse,
                )
            ),
            "angle_mae_deg": float(angle_metrics["angle_mae_deg"]),
            "increment_mae_deg": float(
                angle_metrics["increment_mae_deg"]
            ),
            "span_error_deg": float(angle_metrics["span_error_deg"]),
            "monotonicity_violations": int(
                angle_metrics["monotonicity_violations"]
            ),
        }
        configurations[name] = {
            "runtime_sec": float(record["runtime_sec"]),
            "accepted_edge_count": int(len(record["edges"])),
            "accepted_edge_count_by_gap": _counts_by_gap(record["edges"]),
            "weighting": record["weighting"],
            "gating": record["gating"],
            "predicted": predicted,
            "metrics": metrics,
        }
        if "regularity_weight_px" in record:
            configurations[name]["regularity_weight_px"] = float(
                record["regularity_weight_px"]
            )

    anchor_metrics = configurations["B_gap123_anchor"]["metrics"]
    promotion_candidates = [
        name
        for name in configurations
        if name not in {"A_adjacent", "B_gap123_anchor"}
        and _promotion_ok(
            configurations[name]["metrics"],
            configurations[name]["predicted"],
            anchor_metrics,
        )
    ]

    best_span = min(
        configurations,
        key=lambda name: configurations[name]["metrics"]["span_error_deg"],
    )
    best_angle = min(
        configurations,
        key=lambda name: configurations[name]["metrics"]["angle_mae_deg"],
    )

    report = {
        "schema_version": 1,
        "stage": "turntable_r03b_robust_multibaseline_ab",
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
        "feature_cache_runtime_sec": feature_cache_runtime,
        "initialization": {
            "method": initialization["method"],
            "valid_pair_count": int(initialization["valid_pair_count"]),
            "fallback_pair_count": int(
                initialization["fallback_pair_count"]
            ),
            "initial_span_deg": float(
                np.sum(initialization["initial_deltas_deg"])
            ),
        },
        "anchor_contract": {
            "name": "B_gap123_anchor",
            "ground_truth_used_for_anchor": False,
            "gaps": [1, 2, 3],
        },
        "gap5_diagnostics": diagnostics,
        "gap5_gating": {
            "thresholds": gated["thresholds"],
            "accepted_edge_count": int(len(gated["accepted_edges"])),
            "rejected_edge_count": int(len(gated["rejected_edges"])),
            "accepted_edge_count_by_gap":
                _counts_by_gap(gated["accepted_edges"]),
            "rejected_edges": gated["rejected_edges"],
        },
        "configurations": configurations,
        "comparison": {
            "anchor": "B_gap123_anchor",
            "best_span_error_configuration": best_span,
            "best_angle_mae_configuration": best_angle,
            "promotion_pass": bool(promotion_candidates),
            "promotion_candidates": promotion_candidates,
        },
        "evaluation_ground_truth": {
            "axis_cv": [float(value) for value in gt_axis],
            "transverse_orbit_direction_cv": [
                float(value) for value in gt_transverse
            ],
            "span_deg": float(gt_angles[-1] - gt_angles[0]),
        },
    }

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else dataset.parent.parent / "r03b" / dataset.name
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "r03b_robust_ab_report.json"
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    summary = {
        name: {
            "span_error_deg":
                record["metrics"]["span_error_deg"],
            "angle_mae_deg":
                record["metrics"]["angle_mae_deg"],
            "increment_mae_deg":
                record["metrics"]["increment_mae_deg"],
            "axis_error_deg":
                record["metrics"]["axis_line_error_deg"],
            "orbit_error_deg":
                record["metrics"][
                    "transverse_orbit_line_error_deg"
                ],
            "edges": record["accepted_edge_count"],
            "runtime_sec": record["runtime_sec"],
        }
        for name, record in configurations.items()
    }
    print(json.dumps(summary, indent=2))
    print(json.dumps(report["comparison"], indent=2))
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
