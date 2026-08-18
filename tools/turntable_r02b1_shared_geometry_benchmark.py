"""R0.2b-1 shared geometry benchmark using GT signed pair angles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.workflows.turntable.observations import (
    match_masked_features,
)
from pipeline.workflows.turntable.pose.shared_geometry import (
    directed_angle_error_deg,
    estimate_shared_geometry,
    line_angle_error_deg,
    observable_transverse_orbit,
    prepare_shared_geometry_pair,
)
from pipeline.workflows.turntable.pose.synthetic_geometry import (
    camera_intrinsics_from_ground_truth,
    shared_geometry_from_ground_truth,
)


def _select_left_indices(frame_count, pair_count):
    available = int(frame_count) - 1
    if available < 3:
        raise RuntimeError(
            "Synthetic sequence needs at least 4 frames"
        )
    pair_count = min(
        max(3, int(pair_count)),
        available,
    )
    return sorted(
        {
            int(value)
            for value in np.linspace(
                0,
                available - 1,
                pair_count,
            )
        }
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "R0.2b-1 estimates shared axis + observable "
            "transverse orbit direction. GT supplies K and "
            "signed delta angles only."
        )
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--pair-count",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=120,
    )
    parser.add_argument(
        "--coarse-step",
        type=float,
        default=30.0,
    )
    parser.add_argument("--top-k", type=int, default=8)
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
    intrinsics = camera_intrinsics_from_ground_truth(
        gt["camera"]
    )

    selected = _select_left_indices(
        len(frames),
        args.pair_count,
    )
    prepared = []
    pair_reports = []

    # Estimator input intentionally stops at K + image matches
    # + signed GT delta. GT axis/orbit are not accessed here.
    for left_index in selected:
        right_index = left_index + 1
        left = frames[left_index]
        right = frames[right_index]

        matches = match_masked_features(
            dataset / left["frame"],
            dataset / right["frame"],
            dataset / left["mask"],
            dataset / right["mask"],
        )
        delta_deg = (
            float(right["angle_deg"])
            - float(left["angle_deg"])
        )
        pair = prepare_shared_geometry_pair(
            matches["left_points_px"],
            matches["right_points_px"],
            intrinsics,
            delta_deg,
            max_points=args.max_points,
        )
        prepared.append(pair)
        pair_reports.append(
            {
                "left_index": left_index,
                "right_index": right_index,
                "feature_method": matches["method"],
                "raw_match_count": matches["match_count"],
                "optimization_point_count": pair["count"],
                "known_delta_deg": delta_deg,
            }
        )

    estimate = estimate_shared_geometry(
        prepared,
        coarse_step_deg=args.coarse_step,
        top_k=args.top_k,
        keep_ratio=args.keep_ratio,
    )

    # Evaluation-only GT access starts here.
    gt_geometry = shared_geometry_from_ground_truth(gt)
    gt_axis = gt_geometry["axis_cv"]
    gt_transverse = observable_transverse_orbit(
        gt_axis,
        gt_geometry["orbit_vector_cv"],
    )

    predicted_axis = estimate["axis"]
    predicted_transverse = (
        estimate["transverse_orbit_direction"]
    )

    report = {
        "schema_version": 1,
        "stage": "turntable_r02b1_shared_geometry",
        "estimator_inputs": {
            "ground_truth_axis_used": False,
            "ground_truth_orbit_used": False,
            "ground_truth_delta_angles_used": True,
            "camera_intrinsics_source":
                "synthetic_ground_truth",
        },
        "dataset": str(dataset),
        "optimization_pair_count": len(prepared),
        "optimization_correspondence_count": int(
            sum(pair["count"] for pair in prepared)
        ),
        "predicted": {
            "axis_cv": [
                float(value)
                for value in predicted_axis
            ],
            "transverse_orbit_direction_cv": [
                float(value)
                for value in predicted_transverse
            ],
            "objective_sampson_px":
                estimate["objective_sampson_px"],
            "observable_dof":
                estimate["observable_dof"],
            "coarse_candidate_count":
                estimate["coarse_candidate_count"],
            "refined_seed_count":
                estimate["refined_seed_count"],
            "evaluation_count":
                estimate["evaluation_count"],
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
        },
        "metrics": {
            "axis_line_error_deg":
                line_angle_error_deg(
                    predicted_axis,
                    gt_axis,
                ),
            "axis_directed_error_deg":
                directed_angle_error_deg(
                    predicted_axis,
                    gt_axis,
                ),
            "transverse_orbit_line_error_deg":
                line_angle_error_deg(
                    predicted_transverse,
                    gt_transverse,
                ),
        },
        "pairs": pair_reports,
    }

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (
            dataset.parent.parent
            / "r02b1"
            / dataset.name
        )
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path = (
        output_dir / "shared_geometry_report.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
