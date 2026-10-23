"""R0.2b-2 GT-free joint Turntable pose benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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
from pipeline.workflows.turntable.pose.initialization import (
    initialize_from_generic_essential,
)
from pipeline.workflows.turntable.pose.joint_refine import (
    alternating_joint_refinement,
    estimator_input_contract,
    prepare_joint_pair,
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


def _cumulative_angles(deltas_deg):
    values = [0.0]
    running = 0.0
    for delta in deltas_deg:
        running += float(delta)
        values.append(running)
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "R0.2b-2 estimates shared geometry and all adjacent "
            "Turntable angles without using GT pose or GT span."
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-points", type=int, default=160)
    parser.add_argument(
        "--geometry-pairs",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--min-angle",
        type=float,
        default=0.25,
    )
    parser.add_argument(
        "--max-angle",
        type=float,
        default=20.0,
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
    parser.add_argument(
        "--keep-ratio",
        type=float,
        default=0.70,
    )
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset).resolve()
    gt = json.loads(
        (dataset / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    frames = gt["frames"]

    # Calibration is allowed benchmark input. Pose GT is not.
    intrinsics = camera_intrinsics_from_ground_truth(
        gt["camera"]
    )

    raw_pairs = []
    joint_pairs = []
    match_records = []
    for left_index in range(len(frames) - 1):
        right_index = left_index + 1
        left = frames[left_index]
        right = frames[right_index]
        matches = match_masked_features(
            dataset / left["frame"],
            dataset / right["frame"],
            dataset / left["mask"],
            dataset / right["mask"],
        )
        raw_pair = {
            "left_points_px": matches["left_points_px"],
            "right_points_px": matches["right_points_px"],
        }
        raw_pairs.append(raw_pair)
        joint_pairs.append(
            prepare_joint_pair(
                matches["left_points_px"],
                matches["right_points_px"],
                intrinsics,
                max_points=args.max_points,
            )
        )
        match_records.append(
            {
                "left_index": left_index,
                "right_index": right_index,
                "feature_method": matches["method"],
                "raw_match_count": matches["match_count"],
                "optimization_point_count":
                    joint_pairs[-1]["count"],
            }
        )

    # GT-free initialization begins here. No frame angle is read.
    initialization = initialize_from_generic_essential(
        raw_pairs,
        intrinsics,
        min_angle_deg=args.min_angle,
        max_angle_deg=args.max_angle,
    )

    result = alternating_joint_refinement(
        joint_pairs,
        initialization["axis"],
        initialization["transverse_orbit_direction"],
        initialization["initial_deltas_deg"],
        geometry_pair_count=args.geometry_pairs,
        max_iterations=args.iterations,
        min_angle_deg=args.min_angle,
        max_angle_deg=args.max_angle,
        geometry_coarse_step_deg=args.geometry_coarse_step,
        geometry_top_k=args.geometry_top_k,
        geometry_keep_ratio=args.keep_ratio,
    )

    initial_angles = _cumulative_angles(
        initialization["initial_deltas_deg"]
    )
    predicted_angles = _cumulative_angles(
        result["deltas_deg"]
    )

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

    report = {
        "schema_version": 1,
        "stage": "turntable_r02b2_joint_refinement",
        "estimator_inputs": estimator_input_contract(),
        "dataset": str(dataset),
        "initialization": {
            "method": initialization["method"],
            "valid_pair_count":
                initialization["valid_pair_count"],
            "fallback_pair_count":
                initialization["fallback_pair_count"],
            "fallback_delta_deg":
                initialization["fallback_delta_deg"],
            "forced_360_degree_span": False,
            "initial_span_deg":
                float(np.sum(
                    initialization["initial_deltas_deg"]
                )),
            "records": initialization["records"],
        },
        "predicted": {
            "axis_cv": [
                float(value)
                for value in result["axis"]
            ],
            "transverse_orbit_direction_cv": [
                float(value)
                for value in result[
                    "transverse_orbit_direction"
                ]
            ],
            "deltas_deg": [
                float(value)
                for value in result["deltas_deg"]
            ],
            "angles_deg": [
                float(value)
                for value in predicted_angles
            ],
            "span_deg": float(result["span_deg"]),
            "converged": result["converged"],
            "termination_reason":
                result["termination_reason"],
            "best_state_returned":
                result["best_state_returned"],
            "joint_objective_sampson_px":
                result["joint_objective_sampson_px"],
            "iteration_count":
                result["iteration_count"],
        },
        "initial_angle_metrics":
            angle_sequence_metrics(
                initial_angles,
                ground_truth_angles,
            ),
        "final_angle_metrics":
            angle_sequence_metrics(
                predicted_angles,
                ground_truth_angles,
            ),
        "geometry_metrics": {
            "axis_line_error_deg":
                line_angle_error_deg(
                    result["axis"],
                    gt_axis,
                ),
            "axis_directed_error_deg":
                directed_angle_error_deg(
                    result["axis"],
                    gt_axis,
                ),
            "transverse_orbit_line_error_deg":
                line_angle_error_deg(
                    result[
                        "transverse_orbit_direction"
                    ],
                    gt_transverse,
                ),
        },
        "evaluation_ground_truth": {
            "axis_cv": [
                float(value)
                for value in gt_axis
            ],
            "transverse_orbit_direction_cv": [
                float(value)
                for value in gt_transverse
            ],
            "span_deg": float(
                ground_truth_angles[-1]
                - ground_truth_angles[0]
            ),
        },
        "history": result["history"],
        "accepted_joint_objective_history_px":
            result["accepted_joint_objective_history_px"],
        "geometry_pair_indices":
            result["geometry_pair_indices"],
        "matches": match_records,
    }

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (
            dataset.parent.parent
            / "r02b2"
            / dataset.name
        )
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        output_dir
        / "joint_refinement_report.json"
    )
    prediction_path = (
        output_dir
        / "prediction.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    prediction_path.write_text(
        json.dumps(
            {
                "axis_cv": report["predicted"]["axis_cv"],
                "transverse_orbit_direction_cv":
                    report["predicted"][
                        "transverse_orbit_direction_cv"
                    ],
                "angles_deg":
                    report["predicted"]["angles_deg"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
