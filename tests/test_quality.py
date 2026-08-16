import json
import tempfile
import unittest
from pathlib import Path

from pipeline.run_workspace import create_or_load_run, update_shared_stage, update_route_stage

try:
    from pipeline.quality import generate_quality_report
except ModuleNotFoundError:
    generate_quality_report = None


class TestQualityReport(unittest.TestCase):
    def test_quality_report_writes_json_and_markdown_for_both_routes(self):
        self.assertIsNotNone(generate_quality_report)
        with tempfile.TemporaryDirectory() as d:
            root, _ = create_or_load_run(Path(d) / "runs", "teddy_001")
            update_shared_stage(root, "extract", "ready", frame_count=120)
            update_shared_stage(root, "mask", "ready", mask_count=120)
            update_shared_stage(root, "sparse", "ready", frame_count=120, registered_images=114, points3D=6557, mean_reprojection_error=0.912646)
            update_route_stage(root, "mesh", "texture", "ready")
            update_route_stage(root, "mesh", "glb", "ready", path="output/teddy_001.glb", size_bytes=1024)
            update_route_stage(root, "splat", "training", "ready", steps=10000, raw_path="splat/raw/teddy_001_raw.ply", raw_splats=1000)
            update_route_stage(root, "splat", "cleanup", "ready", raw_splats=1000, clean_splats=250, removed_splats=750, removal_ratio=0.75, foreground_ratio=0.7, min_views=3)
            update_route_stage(root, "splat", "ply", "ready", path="output/teddy_001_splat.ply", size_bytes=2048)
            (root / "output" / "teddy_001.glb").write_bytes(b"x" * 1024)
            (root / "output" / "teddy_001_splat.ply").write_bytes(b"x" * 2048)

            report = generate_quality_report(root)
            self.assertEqual(report["shared"]["registration_rate"], 0.95)
            self.assertEqual(report["splat_route"]["raw_splats"], 1000)
            self.assertEqual(report["splat_route"]["clean_splats"], 250)
            self.assertEqual(report["splat_route"]["removal_ratio"], 0.75)
            self.assertTrue((root / "quality" / "report.json").exists())
            md = (root / "quality" / "report.md").read_text(encoding="utf-8")
            self.assertIn("Videoto3D Quality Report", md)
            self.assertIn("Splat Route", md)
            self.assertIn("75.0%", md)


if __name__ == "__main__": unittest.main()
