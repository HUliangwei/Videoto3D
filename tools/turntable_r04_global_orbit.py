"""Turntable R0.4 engineering-first global orbit CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.workflows.turntable.pose.global_orbit import (
    measurements_from_r03c,
    solve_global_orbit,
)


def _evaluate_if_available(report, angles_deg):
    dataset_text = report.get("dataset")
    if not dataset_text:
        return None
    gt_path = Path(dataset_text) / "ground_truth.json"
    if not gt_path.exists():
        return None

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    gt_angles = np.asarray(
        [float(frame["angle_deg"]) for frame in gt["frames"]],
        dtype=np.float64,
    )
    predicted = np.asarray(angles_deg, dtype=np.float64)
    if len(gt_angles) != len(predicted):
        return None

    gt_aligned = gt_angles - gt_angles[0]
    pred_aligned = predicted - predicted[0]
    increment_gt = np.diff(gt_aligned)
    increment_pred = np.diff(pred_aligned)
    return {
        "ground_truth_used_for_estimation": False,
        "ground_truth_span_deg": float(gt_aligned[-1]),
        "span_error_deg": abs(float(pred_aligned[-1] - gt_aligned[-1])),
        "angle_mae_deg": float(np.mean(np.abs(pred_aligned - gt_aligned))),
        "increment_mae_deg": float(
            np.mean(np.abs(increment_pred - increment_gt))
        ),
        "monotonicity_violations": int(np.sum(np.diff(pred_aligned) <= 0.0)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turntable R0.4 robust free-span global orbit solve."
    )
    parser.add_argument("--r03c-report", required=True)
    parser.add_argument("--output")
    parser.add_argument("--no-gap5", action="store_true")
    parser.add_argument("--irls-iterations", type=int, default=8)
    parser.add_argument("--huber-delta", type=float, default=0.35)
    args = parser.parse_args(argv)

    source_path = Path(args.r03c_report).resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    hypotheses = source.get("hypotheses") or []
    if not hypotheses:
        raise SystemExit("R0.3c report has no hypotheses")
    frame_count = 1 + max(int(item["right_index"]) for item in hypotheses)

    measurement_info = measurements_from_r03c(
        source,
        include_gap5=not args.no_gap5,
    )
    solved = solve_global_orbit(
        frame_count=frame_count,
        measurements=measurement_info["measurements"],
        irls_iterations=args.irls_iterations,
        huber_delta_deg=args.huber_delta,
    )

    r03b_path = Path(source["r03b_report"]).resolve()
    if not r03b_path.exists():
        raise SystemExit("R0.3b report missing: {}".format(r03b_path))
    r03b = json.loads(r03b_path.read_text(encoding="utf-8"))
    shared = r03b["configurations"]["B_gap123_anchor"]["predicted"]

    payload = {
        "schema_version": 1,
        "stage": "turntable_r04_global_orbit_fast_route",
        "estimator_inputs": {
            "ground_truth_axis_used": False,
            "ground_truth_orbit_used": False,
            "ground_truth_angles_used": False,
            "ground_truth_span_used": False,
            "forced_360_degree_span": False,
            "shared_geometry_source": "r03b_B_gap123_anchor",
            "relative_angle_source": "r03c_top1_gap2_gap3_gated_gap5",
        },
        "dataset": source.get("dataset"),
        "r03c_report": str(source_path),
        "r03b_report": str(r03b_path),
        "shared_geometry": {
            "axis_cv": shared["axis_cv"],
            "transverse_orbit_direction_cv":
                shared["transverse_orbit_direction_cv"],
        },
        "measurement_gate": {
            "gap5_residual_threshold_px":
                measurement_info["gap5_residual_threshold_px"],
            "short_residual_median_px":
                measurement_info["short_residual_median_px"],
            "accepted_count": len(measurement_info["measurements"]),
            "rejected_count": len(measurement_info["rejected"]),
            "rejected": measurement_info["rejected"],
        },
        "global_orbit": solved,
    }

    evaluation = _evaluate_if_available(source, solved["angles_deg"])
    if evaluation is not None:
        payload["evaluation"] = evaluation

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        dataset = Path(source["dataset"]).resolve()
        output_path = (
            dataset.parent.parent
            / "r04"
            / dataset.name
            / "r04_global_orbit.json"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    summary = {
        "frame_count": frame_count,
        "span_deg": solved["span_deg"],
        "monotonicity_violations": solved["monotonicity_violations"],
        "measurement_count": solved["measurement_count"],
        "residual_mae_deg": solved["residual_mae_deg"],
        "gap5_rejected": len(measurement_info["rejected"]),
        "evaluation": payload.get("evaluation"),
        "output": str(output_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
