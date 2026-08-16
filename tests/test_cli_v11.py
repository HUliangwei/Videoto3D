import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from pipeline.cli_commands import parse_cli_args
from pipeline.run_workspace import create_or_load_run, load_run_manifest, update_route_stage, update_shared_stage


class TestV11CLI(unittest.TestCase):
    def test_splat_cleanup_options_are_accepted_and_validated(self):
        parsed = parse_cli_args([
            "route", "splat", "--run", "teddy_001",
            "--cleanup-ratio", "0.75", "--cleanup-min-views", "4",
        ])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["options"]["cleanup_ratio"], "0.75")
        self.assertEqual(parsed["options"]["cleanup_min_views"], "4")
        self.assertEqual(parse_cli_args(["run", "splat", "--run", "x", "--cleanup-ratio", "0"])["kind"], "error")
        self.assertEqual(parse_cli_args(["run", "splat", "--run", "x", "--cleanup-min-views", "0"])["kind"], "error")


    def test_run_mask_accepts_browser_box(self):
        parsed = parse_cli_args([
            "run", "mask", "--run", "teddy_001", "--box", "10,20,310,420",
        ])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["options"]["box"], (10, 20, 310, 420))
        self.assertEqual(parse_cli_args(["run", "mask", "--run", "x", "--box", "1,2,3"])["kind"], "error")
        self.assertEqual(parse_cli_args(["run", "sparse", "--run", "x", "--box", "1,2,3,4"])["kind"], "error")

    def test_run_mask_passes_browser_box_to_existing_segmentation_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            run_root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            (run_root / "frames" / "frame_0001.jpg").write_bytes(b"rgb")
            fake_report = {
                "status": "ready", "frame_count": 1, "mask_count": 1,
                "box_xyxy": [10, 20, 310, 420],
            }
            runtime = {"checkpoint": "sam2.pt", "detail": "GPU"}
            with patch.object(app, "WORKSPACE", workspace), patch(
                "app.run_segmentation", return_value=fake_report
            ) as segment:
                code = app.run_mask(runtime, {"run": "teddy_001", "box": (10, 20, 310, 420)})
            self.assertEqual(code, 0)
            self.assertEqual(segment.call_args.kwargs["box"], (10, 20, 310, 420))

    def test_quality_command_requires_run(self):
        self.assertEqual(parse_cli_args(["quality"])["kind"], "error")
        parsed = parse_cli_args(["quality", "--run", "teddy_001"])
        self.assertEqual(parsed["key"], "quality")

    def test_route_splat_can_reuse_training_and_run_cleanup_only(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            for stage in ("extract", "mask", "sparse"):
                update_shared_stage(root, stage, "ready")
            raw = root / "splat" / "raw" / "teddy_001_raw.ply"
            raw.parent.mkdir(parents=True, exist_ok=True); raw.write_bytes(b"raw")
            update_route_stage(root, "splat", "training", "ready", steps=30000, max_splats=2000000, max_resolution=1280, foreground_ratio=0.6, min_foreground_observations=2, raw_path="splat/raw/teddy_001_raw.ply")
            update_route_stage(root, "splat", "cleanup", "pending")
            update_route_stage(root, "splat", "ply", "pending")
            with patch.object(app, "WORKSPACE", workspace), patch("app.run_splat_training") as train, patch("app.run_splat_cleanup", return_value=0) as clean:
                self.assertEqual(app.run_route_splat({"run": "teddy_001"}), 0)
            train.assert_not_called(); clean.assert_called_once()


class TestV11Migration(unittest.TestCase):
    def test_v10_final_splat_is_preserved_as_raw_and_cleanup_becomes_pending(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "teddy_001"; (root / "output").mkdir(parents=True)
            (root / "output" / "teddy_001_splat.ply").write_bytes(b"v10raw")
            manifest = {
                "schema_version": 3, "videoto3d_version": "0.10", "run_id": "teddy_001",
                "created_at": "2026-08-16T00:00:00+00:00", "updated_at": "2026-08-16T00:00:00+00:00",
                "source": {},
                "shared": {s: {"status": "ready"} for s in ("extract", "mask", "sparse")},
                "routes": {
                    "mesh": {s: {"status": "pending"} for s in ("dense", "reconstruct", "refine", "texture", "glb")},
                    "splat": {
                        "object_sparse": {"status": "ready", "foreground_ratio": 0.6, "min_foreground_observations": 2},
                        "training": {"status": "ready", "steps": 10000, "max_splats": 1000000, "max_resolution": 960},
                        "ply": {"status": "ready", "path": "output/teddy_001_splat.ply"},
                    },
                },
            }
            (root / "run.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
            migrated = load_run_manifest(root)
            self.assertEqual(migrated["schema_version"], 4)
            self.assertTrue((root / "splat" / "raw" / "teddy_001_raw.ply").exists())
            self.assertEqual(migrated["routes"]["splat"]["training"]["status"], "ready")
            self.assertEqual(migrated["routes"]["splat"]["cleanup"]["status"], "pending")
            self.assertEqual(migrated["routes"]["splat"]["ply"]["status"], "pending")


if __name__ == "__main__": unittest.main()

class TestV112MeshSettings(unittest.TestCase):
    def test_route_mesh_accepts_safe_mesh_profile(self):
        from pipeline.cli_commands import parse_cli_args
        parsed = parse_cli_args([
            "route", "mesh", "--run", "demo_001",
            "--undistort-max-image-size", "1600",
            "--dense-resolution-level", "1",
            "--dense-number-views", "6",
            "--dense-max-threads", "4",
            "--refine-resolution-level", "2",
        ])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["options"]["dense_number_views"], "6")

    def test_mesh_profile_rejects_negative_auto_values(self):
        from pipeline.cli_commands import parse_cli_args
        parsed = parse_cli_args(["route", "mesh", "--run", "demo_001", "--dense-max-threads", "-1"])
        self.assertEqual(parsed["kind"], "error")
