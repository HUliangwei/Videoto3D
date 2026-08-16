import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.colmap import (
    build_feature_extractor_args,
    build_mapper_args,
    build_model_analyzer_args,
    build_gui_args,
    prepare_gui_model,
    build_sequential_matcher_args,
    _parse_analyzer_stats,
    launch_colmap_gui,
)


class TestColmapPipeline(unittest.TestCase):

    def test_feature_extractor_uses_single_camera_simple_radial(self):
        args = build_feature_extractor_args(
            Path("database.db"),
            Path("frames"),
        )

        self.assertEqual(args[0], "feature_extractor")
        self.assertIn("--ImageReader.single_camera", args)
        self.assertIn("SIMPLE_RADIAL", args)
        self.assertIn("--FeatureExtraction.use_gpu", args)

    def test_feature_extractor_adds_mask_path_when_requested(self):
        args = build_feature_extractor_args(
            Path("database.db"),
            Path("frames"),
            mask_path=Path("masks"),
        )

        self.assertIn("--ImageReader.mask_path", args)
        index = args.index("--ImageReader.mask_path")
        self.assertEqual(args[index + 1], str(Path("masks")))

    def test_feature_extractor_omits_mask_path_by_default(self):
        args = build_feature_extractor_args(
            Path("database.db"),
            Path("frames"),
        )

        self.assertNotIn("--ImageReader.mask_path", args)


    def test_sequential_matcher_is_configured_for_video_frames(self):
        args = build_sequential_matcher_args(
            Path("database.db")
        )

        self.assertEqual(args[0], "sequential_matcher")
        self.assertIn("--SequentialMatching.overlap", args)
        self.assertIn("10", args)
        self.assertIn("--SequentialMatching.quadratic_overlap", args)

    def test_mapper_writes_to_sparse_folder(self):
        args = build_mapper_args(
            Path("database.db"),
            Path("frames"),
            Path("colmap/sparse"),
        )

        self.assertEqual(args[0], "mapper")
        self.assertIn("--output_path", args)
        self.assertIn(str(Path("colmap/sparse")), args)
        self.assertIn("--Mapper.multiple_models", args)

    def test_model_analyzer_uses_model_path(self):
        args = build_model_analyzer_args(
            Path("colmap/sparse/0")
        )

        self.assertEqual(args[0], "model_analyzer")
        self.assertIn("--path", args)
        self.assertIn(str(Path("colmap/sparse/0")), args)


    def test_gui_args_import_sparse_model_and_project_data(self):
        args = build_gui_args(
            Path("colmap/sparse/0"),
            Path("colmap/database.db"),
            Path("frames"),
        )

        self.assertEqual(args[0], "gui")
        self.assertIn("--import_path", args)
        self.assertIn(str(Path("colmap/sparse/0")), args)
        self.assertIn("--database_path", args)
        self.assertIn(str(Path("colmap/database.db")), args)
        self.assertIn("--image_path", args)
        self.assertIn(str(Path("frames")), args)

    def test_parse_analyzer_stats(self):
        output = """
Registered images: 95
Points: 12345
Mean track length: 6.25
Mean reprojection error: 0.71
"""
        stats = _parse_analyzer_stats(output)

        self.assertEqual(stats["registered_images"], 95)
        self.assertEqual(stats["points3D"], 12345)
        self.assertAlmostEqual(stats["mean_track_length"], 6.25)
        self.assertAlmostEqual(stats["mean_reprojection_error"], 0.71)

    def test_prepare_gui_model_copies_only_binary_model_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "sparse" / "0"
            target = root / "viewer_model"
            source.mkdir(parents=True)
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (source / name).write_bytes(name.encode("ascii"))
            (source / "project.ini").write_text("input_path=x\noutput_path=y\n")

            result = prepare_gui_model(source, target)

            self.assertEqual(Path(result), target)
            self.assertTrue((target / "cameras.bin").exists())
            self.assertTrue((target / "images.bin").exists())
            self.assertTrue((target / "points3D.bin").exists())
            self.assertFalse((target / "project.ini").exists())

    def test_colmap_gui_launches_detached(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            colmap = root / "COLMAP.bat"
            colmap.write_text("@echo off", encoding="utf-8")
            model = root / "colmap" / "sparse" / "0"
            model.mkdir(parents=True)
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (model / name).write_bytes(b"x")
            database = root / "colmap" / "database.db"
            database.write_bytes(b"db")
            images = root / "frames"
            images.mkdir()
            with mock.patch("pipeline.colmap.launch_detached") as launch:
                launch.return_value = mock.Mock(pid=2468)
                pid = launch_colmap_gui(colmap, model, database, images, cwd=root)
            self.assertEqual(pid, 2468)
            launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
