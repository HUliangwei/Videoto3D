import json
import tempfile
import unittest
from pathlib import Path

from pipeline.run_workspace import (
    create_or_load_run,
    list_run_summaries,
    load_run_manifest,
    update_route_stage,
    update_shared_stage,
)


class TestRunWorkspaceV10(unittest.TestCase):
    def test_new_run_uses_flat_shared_and_two_route_directories(self):
        with tempfile.TemporaryDirectory() as d:
            root, manifest = create_or_load_run(Path(d) / "runs", "teddy_001")
            self.assertEqual(manifest["schema_version"], 4)
            self.assertEqual(manifest["videoto3d_version"], "0.11")
            self.assertIn("shared", manifest)
            self.assertIn("routes", manifest)
            for name in ("source", "frames", "masks", "segmentation", "colmap", "mesh", "splat", "output", "quality", "logs"):
                self.assertTrue((root / name).is_dir(), name)
            self.assertFalse((root / "shared").exists())
            self.assertFalse((root / "routes").exists())
            for log_group in ("shared", "mesh", "splat"):
                self.assertTrue((root / "logs" / log_group).is_dir())

    def test_v09_layout_migrates_non_destructively_and_preserves_legacy_splat(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "runs" / "teddy_001"
            root.mkdir(parents=True)
            for name in ("mvs_colmap", "openmvs_masks", "openmvs", "blender", "brush", "output", "logs"):
                (root / name).mkdir()
            (root / "openmvs" / "object.obj").write_bytes(b"obj")
            (root / "brush" / "recipe.json").write_text("{}", encoding="utf-8")
            (root / "output" / "teddy_001.glb").write_bytes(b"glb")
            (root / "output" / "teddy_001_splat.ply").write_bytes(b"ply")
            old = {
                "schema_version": 2,
                "videoto3d_version": "0.9",
                "run_id": "teddy_001",
                "created_at": "2026-08-16T00:00:00+00:00",
                "updated_at": "2026-08-16T00:00:00+00:00",
                "source": {},
                "stages": {
                    "extract": {"status": "ready", "frame_count": 120},
                    "mask": {"status": "ready", "mask_count": 120},
                    "sparse": {"status": "ready", "registered_images": 114},
                    "mesh": {"status": "ready"},
                    "glb": {"status": "ready", "path": "output/teddy_001.glb"},
                    "splat": {"status": "ready", "path": "output/teddy_001_splat.ply"},
                },
            }
            (root / "run.json").write_text(json.dumps(old), encoding="utf-8")

            manifest = load_run_manifest(root)
            self.assertEqual(manifest["schema_version"], 4)
            self.assertTrue((root / "mesh" / "openmvs" / "object.obj").exists())
            self.assertTrue((root / "splat" / "legacy_v09" / "recipe.json").exists())
            self.assertTrue((root / "splat" / "legacy_v09" / "teddy_001_splat.ply").exists())
            self.assertTrue((root / "output" / "teddy_001.glb").exists())
            self.assertEqual(manifest["shared"]["sparse"]["status"], "ready")
            self.assertEqual(manifest["routes"]["mesh"]["glb"]["status"], "ready")
            self.assertEqual(manifest["routes"]["splat"]["training"]["status"], "pending")
            self.assertEqual(manifest["routes"]["splat"]["cleanup"]["status"], "pending")
            self.assertEqual(manifest["routes"]["splat"]["ply"]["status"], "pending")

    def test_summaries_distinguish_shared_mesh_and_splat_routes(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = create_or_load_run(Path(d) / "runs", "teddy_001")
            update_shared_stage(root, "extract", "ready", frame_count=120)
            update_shared_stage(root, "mask", "ready")
            update_shared_stage(root, "sparse", "ready")
            update_route_stage(root, "mesh", "glb", "ready")
            summaries = list_run_summaries(Path(d) / "runs")
            self.assertEqual(summaries[0]["shared_status"], "READY")
            self.assertEqual(summaries[0]["mesh_status"], "COMPLETE")
            self.assertEqual(summaries[0]["splat_status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
