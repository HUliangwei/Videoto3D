"""Score Turntable pose predictions against synthetic ground truth."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from pipeline.workflows.turntable.benchmark.metrics import angle_sequence_metrics, axis_error_deg

def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ground-truth", required=True)
    p.add_argument("--prediction", required=True)
    p.add_argument("--output")
    args = p.parse_args(argv)
    gt, pred = _load(args.ground_truth), _load(args.prediction)
    gt_angles = [f["angle_deg"] for f in gt["frames"]]
    metrics = angle_sequence_metrics(pred["angles_deg"], gt_angles)
    if "axis" in pred:
        metrics["axis_error_deg"] = axis_error_deg(pred["axis"], gt["rotation_axis_world"])
    payload = {"schema_version": 1, "metrics": metrics}
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
