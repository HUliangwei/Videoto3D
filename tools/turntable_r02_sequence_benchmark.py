"""Evaluate adjacent-pair R0.2a angles across a synthetic sequence."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.workflows.turntable.benchmark.metrics import angle_sequence_metrics
from pipeline.workflows.turntable.observations import match_masked_features
from pipeline.workflows.turntable.pose import fit_structured_angle, shared_geometry_from_ground_truth

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-angle", type=float, default=30.0)
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    dataset = Path(args.dataset).resolve()
    gt = json.loads((dataset/"ground_truth.json").read_text(encoding="utf-8"))
    frames = gt["frames"]
    geometry = shared_geometry_from_ground_truth(gt)
    predicted = [0.0]
    pairs = []
    for left_index in range(len(frames)-1):
        right_index = left_index + 1
        left, right = frames[left_index], frames[right_index]
        matches = match_masked_features(dataset/left["frame"], dataset/right["frame"], dataset/left["mask"], dataset/right["mask"])
        estimate = fit_structured_angle(
            matches["left_points_px"], matches["right_points_px"],
            geometry["intrinsics"], geometry["axis_cv"], geometry["orbit_vector_cv"],
            max_abs_angle_deg=args.max_angle,
        )
        delta = float(estimate["signed_angle_deg"])
        predicted.append(predicted[-1] + delta)
        pairs.append({
            "left_index": left_index, "right_index": right_index,
            "match_count": matches["match_count"], "feature_method": matches["method"],
            "predicted_delta_deg": delta, "median_sampson_px": estimate["median_sampson_px"],
        })
    gt_angles = [float(item["angle_deg"]) for item in frames]
    report = {
        "schema_version": 1,
        "stage": "turntable_r02a_structured_sequence",
        "shared_geometry_source": "synthetic_ground_truth",
        "dataset": str(dataset),
        "metrics": angle_sequence_metrics(predicted, gt_angles),
        "predicted_angles_deg": predicted,
        "pairs": pairs,
    }
    output_dir = Path(args.output_dir).resolve() if args.output_dir else dataset.parent.parent/"r02a"/dataset.name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"structured_sequence_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir/"prediction.json").write_text(json.dumps({"angles_deg":predicted}, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Report:", output_dir/"structured_sequence_report.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
