"""Fast R0.3c benchmark for anchor-independent pair-angle hypotheses."""
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

from pipeline.workflows.turntable.observations import match_masked_features
from pipeline.workflows.turntable.observations.graph import edge_schedule
from pipeline.workflows.turntable.pose.multi_hypothesis import generate_pair_hypotheses
from pipeline.workflows.turntable.pose.multibaseline import prepare_graph_edges
from pipeline.workflows.turntable.pose.synthetic_geometry import (
    camera_intrinsics_from_ground_truth,
)


def _parse_gaps(text):
    gaps = tuple(sorted(set(int(v.strip()) for v in str(text).split(",") if v.strip())))
    if not gaps or any(v <= 0 for v in gaps):
        raise argparse.ArgumentTypeError("gaps must be positive comma-separated integers")
    return gaps


def _default_r03b_report(dataset):
    return (
        dataset.parent.parent
        / "r03b"
        / dataset.name
        / "r03b_robust_ab_report.json"
    )


def _load_shared_geometry(report_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    block = report["configurations"]["B_gap123_anchor"]["predicted"]
    return (
        np.asarray(block["axis_cv"], dtype=np.float64),
        np.asarray(block["transverse_orbit_direction_cv"], dtype=np.float64),
    )


def _match_edges(dataset, frames, gaps):
    accepted = []
    rejected = []
    for left_index, right_index in edge_schedule(len(frames), gaps):
        left = frames[left_index]
        right = frames[right_index]
        try:
            matched = match_masked_features(
                dataset / left["frame"],
                dataset / right["frame"],
                dataset / left["mask"],
                dataset / right["mask"],
            )
        except RuntimeError as exc:
            rejected.append({
                "left_index": int(left_index),
                "right_index": int(right_index),
                "gap": int(right_index - left_index),
                "reason": "match_failed",
                "error": str(exc),
            })
            continue
        count = int(matched.get("match_count", 0))
        if count < 8:
            rejected.append({
                "left_index": int(left_index),
                "right_index": int(right_index),
                "gap": int(right_index - left_index),
                "raw_match_count": count,
                "reason": "too_few_correspondences",
            })
            continue
        accepted.append({
            "left_index": int(left_index),
            "right_index": int(right_index),
            "gap": int(right_index - left_index),
            "left_points_px": matched["left_points_px"],
            "right_points_px": matched["right_points_px"],
            "feature_method": matched.get("method", "UNKNOWN"),
            "raw_match_count": count,
        })
    return accepted, rejected


def _metric_block(errors):
    if not errors:
        return {
            "edge_count": 0,
            "top1_mae_deg": None,
            "topk_oracle_mae_deg": None,
            "topk_recall_0p25": None,
            "topk_recall_0p50": None,
            "topk_recall_1p00": None,
        }
    top1 = np.asarray([item["top1_error_deg"] for item in errors], dtype=np.float64)
    oracle = np.asarray([item["oracle_error_deg"] for item in errors], dtype=np.float64)
    return {
        "edge_count": int(len(errors)),
        "top1_mae_deg": float(np.mean(top1)),
        "topk_oracle_mae_deg": float(np.mean(oracle)),
        "topk_recall_0p25": float(np.mean(oracle <= 0.25)),
        "topk_recall_0p50": float(np.mean(oracle <= 0.50)),
        "topk_recall_1p00": float(np.mean(oracle <= 1.00)),
        "top1_median_error_deg": float(np.median(top1)),
        "topk_oracle_median_error_deg": float(np.median(oracle)),
        "topk_oracle_max_error_deg": float(np.max(oracle)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turntable R0.3c anchor-independent multi-hypothesis pair benchmark."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--r03b-report")
    parser.add_argument("--gaps", type=_parse_gaps, default=(2, 3, 5))
    parser.add_argument("--max-points", type=int, default=160)
    parser.add_argument("--min-angle", type=float, default=0.25)
    parser.add_argument("--max-angle", type=float, default=60.0)
    parser.add_argument("--coarse-step", type=float, default=0.5)
    parser.add_argument("--refine-step", type=float, default=0.05)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-separation", type=float, default=0.5)
    parser.add_argument("--keep-ratio", type=float, default=0.70)
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset).resolve()
    gt_path = dataset / "ground_truth.json"
    if not gt_path.exists():
        raise SystemExit("ground_truth.json missing: {}".format(gt_path))

    # The file contains synthetic calibration and frame paths. Angle fields are
    # deliberately not accessed until all hypotheses have been generated.
    gt_doc = json.loads(gt_path.read_text(encoding="utf-8"))
    frames = gt_doc["frames"]
    intrinsics = camera_intrinsics_from_ground_truth(gt_doc["camera"])

    report_path = (
        Path(args.r03b_report).resolve()
        if args.r03b_report
        else _default_r03b_report(dataset).resolve()
    )
    if not report_path.exists():
        raise SystemExit(
            "R0.3b report missing: {}. Pass --r03b-report explicitly.".format(report_path)
        )
    axis, transverse = _load_shared_geometry(report_path)

    started = time.perf_counter()
    raw_edges, rejected_edges = _match_edges(dataset, frames, args.gaps)
    match_runtime = time.perf_counter() - started
    if not raw_edges:
        raise SystemExit("No valid observation edges.")

    prepared = prepare_graph_edges(
        raw_edges,
        intrinsics,
        max_points=args.max_points,
    )

    hypothesis_started = time.perf_counter()
    hypotheses = []
    for edge in prepared:
        hypotheses.append(
            generate_pair_hypotheses(
                edge,
                axis,
                transverse,
                min_angle_deg=args.min_angle,
                max_angle_deg=args.max_angle,
                coarse_step_deg=args.coarse_step,
                refine_step_deg=args.refine_step,
                top_k=args.top_k,
                min_separation_deg=args.min_separation,
                keep_ratio=args.keep_ratio,
            )
        )
    hypothesis_runtime = time.perf_counter() - hypothesis_started

    # Evaluation-only access to synthetic angle ground truth starts here.
    gt_angles = [float(frame["angle_deg"]) for frame in frames]
    evaluated_edges = []
    by_gap = {}
    for result in hypotheses:
        left = int(result["left_index"])
        right = int(result["right_index"])
        true_angle = float(gt_angles[right] - gt_angles[left])
        candidates = result["candidates"]
        top1_error = abs(float(candidates[0]["angle_deg"]) - true_angle)
        oracle_error = min(abs(float(c["angle_deg"]) - true_angle) for c in candidates)
        evaluation = {
            "left_index": left,
            "right_index": right,
            "gap": int(result["gap"]),
            "true_relative_angle_deg": true_angle,
            "top1_error_deg": float(top1_error),
            "oracle_error_deg": float(oracle_error),
        }
        evaluated_edges.append(evaluation)
        by_gap.setdefault(int(result["gap"]), []).append(evaluation)

    overall_metrics = _metric_block(evaluated_edges)
    per_gap_metrics = {
        str(gap): _metric_block(records)
        for gap, records in sorted(by_gap.items())
    }

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else dataset.parent.parent / "r03c" / dataset.name
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "r03c_hypothesis_report.json"

    report = {
        "schema_version": 1,
        "stage": "turntable_r03c_anchor_independent_multi_hypothesis",
        "estimator_inputs": {
            "ground_truth_axis_used": False,
            "ground_truth_orbit_used": False,
            "ground_truth_angles_used_for_hypotheses": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
            "shared_geometry_source": "r03b_B_gap123_anchor",
            "anchor_trajectory_angles_used_for_pair_search": False,
            "camera_intrinsics_source": "synthetic_ground_truth_calibration_only",
        },
        "dataset": str(dataset),
        "r03b_report": str(report_path),
        "search": {
            "gaps": [int(v) for v in args.gaps],
            "min_angle_deg": float(args.min_angle),
            "max_angle_deg": float(args.max_angle),
            "coarse_step_deg": float(args.coarse_step),
            "refine_step_deg": float(args.refine_step),
            "top_k": int(args.top_k),
            "min_separation_deg": float(args.min_separation),
            "keep_ratio": float(args.keep_ratio),
            "max_points": int(args.max_points),
        },
        "runtime_sec": {
            "feature_matching": float(match_runtime),
            "hypothesis_generation": float(hypothesis_runtime),
            "total": float(match_runtime + hypothesis_runtime),
        },
        "edge_counts": {
            "attempted": int(len(raw_edges) + len(rejected_edges)),
            "accepted": int(len(raw_edges)),
            "rejected": int(len(rejected_edges)),
        },
        "rejected_edges": rejected_edges,
        "hypotheses": hypotheses,
        "evaluation": {
            "overall": overall_metrics,
            "per_gap": per_gap_metrics,
            "edges": evaluated_edges,
        },
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "accepted_edges": len(raw_edges),
        "rejected_edges": len(rejected_edges),
        "runtime_sec": report["runtime_sec"],
        "overall": overall_metrics,
        "per_gap": per_gap_metrics,
    }, indent=2))
    print("Report:", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
