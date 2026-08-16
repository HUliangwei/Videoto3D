import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.brush import build_brush_train_command, build_brush_view_command, prepare_brush_dataset


class TestBrushPipeline(unittest.TestCase):
    def test_prepare_brush_dataset_stages_rgb_masks_and_filtered_colmap(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "teddy_001"
            (run / "frames").mkdir(parents=True); (run / "masks").mkdir()
            sparse = run / "colmap" / "sparse" / "0"; sparse.mkdir(parents=True)
            (run / "frames" / "frame_0001.jpg").write_bytes(b"rgb")
            (run / "masks" / "frame_0001.jpg.png").write_bytes(b"mask")
            for name in ("cameras.bin", "images.bin", "points3D.bin"): (sparse / name).write_bytes(name.encode("ascii"))

            def fake_filter(source_model, masks_dir, output_model, report_path, **kwargs):
                output_model.mkdir(parents=True, exist_ok=True)
                for name in ("cameras.bin", "images.bin", "points3D.bin"):
                    (output_model / name).write_bytes((source_model / name).read_bytes())
                Path(report_path).write_text("{}", encoding="utf-8")
                return {"source_points": 100, "kept_points": 50, "removed_points": 50}

            with patch("pipeline.brush.filter_colmap_points_by_masks", side_effect=fake_filter) as filt:
                result = prepare_brush_dataset(run, min_kept_points=1)
            dataset = Path(result["dataset_root"])
            self.assertEqual(dataset, run / "splat" / "dataset")
            self.assertTrue((dataset / "images" / "frame_0001.jpg").exists())
            self.assertTrue((dataset / "masks" / "frame_0001.jpg.png").exists())
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                self.assertTrue((dataset / "sparse" / "0" / name).exists())
            self.assertEqual(filt.call_args.kwargs["foreground_ratio"], 0.60)
            self.assertEqual(result["object_sparse"]["kept_points"], 50)

    def test_train_command_uses_headless_profile_and_run_local_exports(self):
        command = build_brush_train_command(Path("brush.exe"), Path("splat/dataset"), "teddy_001", 30000, 2000000, 1280)
        self.assertNotIn("--with-viewer", command)
        pairs = dict(zip(command[2::2], command[3::2]))
        self.assertEqual(pairs["--total-train-iters"], "30000")
        self.assertEqual(pairs["--export-path"], "./exports/")
        self.assertEqual(pairs["--export-name"], "teddy_001_{iter}.ply")

    def test_view_command_explicitly_enables_brush_viewer(self):
        command = build_brush_view_command(Path("brush.exe"), Path("output/teddy_001_splat.ply"))
        self.assertEqual(command[-1], "--with-viewer")

    def test_training_preserves_canonical_raw_output_before_cleanup(self):
        import tempfile
        from unittest.mock import patch
        from pipeline.brush import run_brush_training
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "run"
            (root / "frames").mkdir(parents=True); (root / "masks").mkdir(); (root / "colmap" / "sparse" / "0").mkdir(parents=True)
            (root / "frames" / "frame_0001.jpg").write_bytes(b"rgb")
            (root / "masks" / "frame_0001.jpg.png").write_bytes(b"mask")
            for n in ("cameras.bin", "images.bin", "points3D.bin"): (root / "colmap" / "sparse" / "0" / n).write_bytes(b"x")
            brush = root / "brush.exe"; brush.write_bytes(b"exe")
            def fake_stage(*args, **kwargs):
                br = root / "splat"; ds = br / "dataset"; (ds / "sparse" / "0").mkdir(parents=True, exist_ok=True)
                rep = br / "object_sparse_report.json"; rep.write_text("{}", encoding="utf-8")
                return {"brush_root": str(br), "dataset_root": str(ds), "object_sparse_report": str(rep), "object_sparse": {"source_points": 10, "kept_points": 5}}
            def fake_stream(command, cwd, log_path):
                ex = Path(cwd) / "exports"; ex.mkdir(parents=True, exist_ok=True); (ex / "teddy_001_10000.ply").write_bytes(b"rawply")
            with patch("pipeline.brush.prepare_brush_dataset", side_effect=fake_stage), patch("pipeline.brush._stream_process", side_effect=fake_stream):
                result = run_brush_training(brush, root, "teddy_001", steps=10000)
            self.assertEqual(Path(result["raw_ply"]), root / "splat" / "raw" / "teddy_001_raw.ply")
            self.assertEqual(Path(result["raw_ply"]).read_bytes(), b"rawply")
            self.assertFalse((root / "output" / "teddy_001_splat.ply").exists())


if __name__ == "__main__": unittest.main()
