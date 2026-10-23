"""Evaluate one synthetic image pair with the R0.2a structured estimator."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.workflows.turntable.observations import match_masked_features
from pipeline.workflows.turntable.pose import fit_structured_angle, ground_truth_delta_deg, shared_geometry_from_ground_truth

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--left", type=int, default=0)
    parser.add_argument("--right", type=int, default=1)
    parser.add_argument("--max-angle", type=float, default=30.0)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    root = Path(args.dataset).resolve()
    gt = json.loads((root/"ground_truth.json").read_text(encoding="utf-8"))
    frames = gt["frames"]
    left, right = frames[args.left], frames[args.right]
    matches = match_masked_features(root/left["frame"], root/right["frame"], root/left["mask"], root/right["mask"])
    geometry = shared_geometry_from_ground_truth(gt)
    estimate = fit_structured_angle(
        matches["left_points_px"], matches["right_points_px"],
        geometry["intrinsics"], geometry["axis_cv"], geometry["orbit_vector_cv"],
        max_abs_angle_deg=args.max_angle,
    )
    gt_delta = ground_truth_delta_deg(gt, args.left, args.right)
    report = {
        "schema_version": 1,
        "stage": "turntable_r02a_structured_pair",
        "shared_geometry_source": "synthetic_ground_truth",
        "feature_method": matches["method"],
        "left_index": args.left, "right_index": args.right,
        "match_count": matches["match_count"],
        "ground_truth_delta_deg": gt_delta,
        "predicted_delta_deg": estimate["signed_angle_deg"],
        "angle_error_deg": abs(estimate["signed_angle_deg"] - gt_delta),
        "median_sampson_px": estimate["median_sampson_px"],
    }
    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
