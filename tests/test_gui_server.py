import json
from pathlib import Path
import unittest

from gui.control.server.service import (
    get_run_detail,
    list_runs,
    resolve_run_asset,
)


class GuiServerServiceTests(unittest.TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run_root = self.root / "workspace" / "runs" / "teddy_001"
        (self.run_root / "output").mkdir(parents=True)
        (self.run_root / "quality").mkdir(parents=True)
        manifest = {
            "schema_version": 4,
            "videoto3d_version": "0.11",
            "run_id": "teddy_001",
            "created_at": "2026-08-16T00:00:00+00:00",
            "updated_at": "2026-08-16T01:00:00+00:00",
            "source": {"local_file": "source/teddy.mp4"},
            "shared": {
                "extract": {"status": "ready", "frame_count": 120},
                "mask": {"status": "ready", "mask_count": 120},
                "sparse": {"status": "ready", "registered_images": 114, "total_images": 120, "points3D": 6557},
            },
            "routes": {
                "mesh": {
                    "dense": {"status": "ready"},
                    "reconstruct": {"status": "ready"},
                    "refine": {"status": "ready"},
                    "texture": {"status": "ready"},
                    "glb": {"status": "ready", "path": "output/teddy_001.glb"},
                },
                "splat": {
                    "training": {"status": "ready", "steps": 30000},
                    "cleanup": {"status": "ready", "raw_splats": 1000, "clean_splats": 300},
                    "ply": {"status": "ready", "path": "output/teddy_001_splat.ply"},
                },
            },
        }
        (self.run_root / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.run_root / "quality" / "report.json").write_text(
            json.dumps({"run_id": "teddy_001", "shared": {"registration_rate": 0.95}}),
            encoding="utf-8",
        )
        (self.run_root / "output" / "teddy_001.glb").write_bytes(b"glTF")
        (self.run_root / "output" / "teddy_001_splat.ply").write_bytes(b"ply\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_runs_returns_dual_route_summary(self):
        rows = list_runs(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], "teddy_001")
        self.assertEqual(rows[0]["shared_status"], "READY")
        self.assertEqual(rows[0]["mesh_status"], "COMPLETE")
        self.assertEqual(rows[0]["splat_status"], "COMPLETE")
        self.assertTrue(rows[0]["assets"]["glb"])
        self.assertTrue(rows[0]["assets"]["splat"])

    def test_run_detail_includes_quality_and_asset_urls(self):
        detail = get_run_detail(self.root, "teddy_001")
        self.assertEqual(detail["run_id"], "teddy_001")
        self.assertEqual(detail["quality"]["shared"]["registration_rate"], 0.95)
        self.assertEqual(detail["assets"]["glb"], "/api/runs/teddy_001/assets/glb")
        self.assertEqual(detail["assets"]["splat"], "/api/runs/teddy_001/assets/splat")

    def test_resolve_asset_rejects_manifest_escape(self):
        manifest_path = self.run_root / "run.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["routes"]["mesh"]["glb"]["path"] = "../../secret.glb"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        (self.root / "workspace" / "secret.glb").write_bytes(b"secret")
        with self.assertRaises(ValueError):
            resolve_run_asset(self.root, "teddy_001", "glb")

    def test_resolve_asset_returns_existing_known_output(self):
        path = resolve_run_asset(self.root, "teddy_001", "splat")
        self.assertEqual(path.name, "teddy_001_splat.ply")


if __name__ == "__main__":
    unittest.main()
