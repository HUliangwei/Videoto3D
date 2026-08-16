import json
import tempfile
import unittest
from pathlib import Path

from pipeline.run_workspace import (
    create_or_load_run,
    list_run_summaries,
    load_run_manifest,
    resolve_run_root,
    update_shared_stage,
    validate_run_id,
)


class TestRunWorkspace(unittest.TestCase):
    def test_run_id_rejects_path_traversal_and_accepts_slug(self):
        self.assertEqual(validate_run_id("teddy_001"), "teddy_001")
        for bad in ("../evil", "a/b", "", ".", "..", "a b"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): validate_run_id(bad)

    def test_create_run_builds_manifest_and_directories(self):
        with tempfile.TemporaryDirectory() as d:
            runs = Path(d) / "runs"; root, manifest = create_or_load_run(runs, "teddy_001")
            self.assertEqual(root, runs / "teddy_001")
            self.assertEqual(manifest["schema_version"], 4)
            self.assertIn("shared", manifest); self.assertIn("routes", manifest)
            for name in ("source", "frames", "masks", "segmentation", "colmap", "mesh", "splat", "output", "quality", "logs"):
                self.assertTrue((root / name).is_dir(), name)

    def test_stage_updates_are_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = create_or_load_run(Path(d) / "runs", "teddy_001")
            update_shared_stage(root, "extract", "ready", frame_count=120)
            manifest = load_run_manifest(root)
            self.assertEqual(manifest["shared"]["extract"]["status"], "ready")
            self.assertEqual(manifest["shared"]["extract"]["frame_count"], 120)

    def test_list_run_summaries_reads_multiple_runs(self):
        with tempfile.TemporaryDirectory() as d:
            runs = Path(d) / "runs"
            for run_id in ("teddy_001", "cup_001"):
                root, _ = create_or_load_run(runs, run_id)
                update_shared_stage(root, "extract", "ready", frame_count=120)
            summaries = list_run_summaries(runs)
            self.assertEqual([x["run_id"] for x in summaries], ["cup_001", "teddy_001"])
            self.assertIn("splat_status", summaries[0])

    def test_loading_v08_manifest_migrates_to_v11_schema(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "runs" / "teddy_001"; root.mkdir(parents=True)
            old = {
                "schema_version": 1, "videoto3d_version": "0.8", "run_id": "teddy_001",
                "created_at": "2026-08-16T00:00:00+00:00", "updated_at": "2026-08-16T00:00:00+00:00", "source": {},
                "stages": {s: {"status": "ready"} for s in ("extract", "mask", "sparse", "mesh", "glb")},
            }
            (root / "run.json").write_text(json.dumps(old), encoding="utf-8")
            manifest = load_run_manifest(root)
            self.assertEqual(manifest["schema_version"], 4)
            self.assertEqual(manifest["videoto3d_version"], "0.11")
            self.assertEqual(manifest["routes"]["splat"]["ply"]["status"], "pending")


if __name__ == "__main__": unittest.main()
