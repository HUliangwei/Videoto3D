import unittest
from pathlib import Path

from pipeline.openmvs import (
    build_image_undistorter_args,
    build_interface_colmap_args,
    build_densify_args,
    is_retryable_densify_exit_code,
    build_reconstruct_mesh_args,
    build_refine_mesh_args,
    build_texture_mesh_args,
)


class TestOpenMVSMeshPipeline(unittest.TestCase):

    def test_undistorter_exports_colmap_workspace(self):
        args = build_image_undistorter_args(
            image_path=Path("frames"),
            input_model=Path("colmap/sparse/0"),
            output_path=Path("colmap/undistorted"),
        )

        self.assertEqual(args[0], "image_undistorter")
        self.assertIn("--output_type", args)
        self.assertIn("COLMAP", args)
        self.assertIn("--input_path", args)
        self.assertIn(str(Path("colmap/sparse/0")), args)

    def test_interface_colmap_uses_undistorted_root_and_images(self):
        args = build_interface_colmap_args(
            undistorted_root=Path("colmap/undistorted"),
            undistorted_images=Path("colmap/undistorted/images"),
            openmvs_dir=Path("openmvs"),
        )

        self.assertIn("--input-file", args)
        self.assertIn(
            str(Path("colmap/undistorted")),
            args,
        )
        self.assertNotIn(
            str(Path("colmap/undistorted/sparse")),
            args,
        )
        self.assertIn("--image-folder", args)
        self.assertIn(
            str(Path("colmap/undistorted/images")),
            args,
        )
        self.assertIn(
            str(Path("openmvs") / "scene.mvs"),
            args,
        )

    def test_densify_uses_scene_and_writes_dense_scene(self):
        args = build_densify_args(
            Path("openmvs")
        )

        self.assertIn(
            str(Path("openmvs") / "scene.mvs"),
            args,
        )
        self.assertIn(
            str(Path("openmvs") / "scene_dense.mvs"),
            args,
        )
        self.assertIn("--archive-type", args)
        self.assertIn("-1", args)

    def test_reconstruct_mesh_uses_dense_scene_and_outputs_ply(self):
        args = build_reconstruct_mesh_args(
            Path("openmvs")
        )

        self.assertIn(
            str(Path("openmvs") / "scene_dense.mvs"),
            args,
        )
        self.assertIn(
            str(Path("openmvs") / "scene_mesh.ply"),
            args,
        )
        self.assertNotIn(
            str(Path("openmvs") / "scene_mesh.mvs"),
            args,
        )

    def test_refine_mesh_uses_dense_scene_and_mesh_file(self):
        args = build_refine_mesh_args(
            Path("openmvs")
        )

        self.assertIn(
            str(Path("openmvs") / "scene_dense.mvs"),
            args,
        )
        self.assertIn("--mesh-file", args)
        self.assertIn(
            str(Path("openmvs") / "scene_mesh.ply"),
            args,
        )
        self.assertIn(
            str(Path("openmvs") / "scene_refined.ply"),
            args,
        )
        self.assertIn("--resolution-level", args)
        self.assertIn("1", args)

    def test_texture_mesh_uses_dense_scene_and_refined_mesh(self):
        args = build_texture_mesh_args(
            Path("openmvs")
        )

        self.assertIn(
            str(Path("openmvs") / "scene_dense.mvs"),
            args,
        )
        self.assertIn("--mesh-file", args)
        self.assertIn(
            str(Path("openmvs") / "scene_refined.ply"),
            args,
        )
        self.assertIn("--export-type", args)
        self.assertIn("obj", args)
        self.assertIn(
            str(Path("openmvs") / "object.obj"),
            args,
        )


    def test_safe_densify_args_reduce_workload(self):
        args = build_densify_args(
            Path("openmvs"),
            safe_mode=True,
        )

        self.assertIn("--resolution-level", args)
        self.assertIn("1", args)
        self.assertIn("--number-views", args)
        self.assertIn("8", args)
        self.assertIn("--max-threads", args)
        idx = args.index("--max-threads")
        self.assertIn(args[idx + 1], ("1", "2"))

    def test_default_densify_args_keep_original_quality_mode(self):
        args = build_densify_args(
            Path("openmvs"),
            safe_mode=False,
        )

        self.assertNotIn("--resolution-level", args)
        self.assertNotIn("--number-views", args)
        self.assertNotIn("--max-threads", args)

    def test_windows_access_violation_is_retryable(self):
        self.assertTrue(
            is_retryable_densify_exit_code(
                3221225477
            )
        )
        self.assertTrue(
            is_retryable_densify_exit_code(
                -1073741819
            )
        )
        self.assertFalse(
            is_retryable_densify_exit_code(
                1
            )
        )


    def test_dense_outputs_ready(self):
        from pipeline.openmvs import dense_outputs_ready
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "scene_dense.mvs").write_text("ok")
            (p / "scene_dense.ply").write_bytes(b"x" * 2048)
            self.assertTrue(dense_outputs_ready(p))

    def test_thread_policy(self):
        from pipeline.openmvs import choose_densify_thread_count
        self.assertTrue(
            choose_densify_thread_count().isdigit()
        )

    def test_masked_densify_uses_openmvs_mask_path_and_ignores_black(self):
        args = build_densify_args(
            Path("openmvs"),
            mask_path=Path("openmvs_masks"),
        )
        self.assertIn("--mask-path", args)
        self.assertIn(str(Path("openmvs_masks")), args)
        self.assertIn("--ignore-mask-label", args)
        idx = args.index("--ignore-mask-label")
        self.assertEqual(args[idx + 1], "0")

    def test_safe_densify_keeps_mask_flags(self):
        args = build_densify_args(
            Path("openmvs"),
            safe_mode=True,
            mask_path=Path("openmvs_masks"),
        )
        self.assertIn("--mask-path", args)
        self.assertIn("--ignore-mask-label", args)

    def test_masked_texture_ignores_black_mask_label(self):
        args = build_texture_mesh_args(
            Path("openmvs"),
            masked=True,
        )
        self.assertIn("--ignore-mask-label", args)
        idx = args.index("--ignore-mask-label")
        self.assertEqual(args[idx + 1], "0")

    def test_texture_workaround_disables_seam_leveling_for_openmvs_240(self):
        args = build_texture_mesh_args(
            Path("openmvs"),
            masked=True,
        )
        self.assertIn("--global-seam-leveling", args)
        self.assertEqual(args[args.index("--global-seam-leveling") + 1], "0")
        self.assertIn("--local-seam-leveling", args)
        self.assertEqual(args[args.index("--local-seam-leveling") + 1], "0")

    def test_texture_cache_requires_current_recipe_marker(self):
        import json
        import tempfile
        from pipeline.openmvs import TEXTURE_RECIPE_VERSION, texture_outputs_ready

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "object.obj").write_bytes(b"obj")
            (root / "object.mtl").write_bytes(b"mtl")
            (root / "object_material_00_map_Kd.jpg").write_bytes(b"texture")

            self.assertFalse(texture_outputs_ready(root))

            (root / "texture_recipe.json").write_text(
                json.dumps({"version": TEXTURE_RECIPE_VERSION}),
                encoding="utf-8",
            )
            self.assertTrue(texture_outputs_ready(root))

    def test_high_core_safe_retry_is_single_thread(self):
        from unittest.mock import patch
        from pipeline.openmvs import choose_densify_thread_count
        with patch("os.cpu_count", return_value=32):
            self.assertEqual(choose_densify_thread_count(), "1")

    def test_resume_skips_completed_openmvs_stages(self):
        import tempfile
        from unittest.mock import patch
        from pipeline.openmvs import run_mesh_pipeline

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            colmap_path = root / "COLMAP.bat"
            colmap_path.write_text("stub")
            openmvs_bin = root / "bin"
            openmvs_bin.mkdir()
            for name in (
                "InterfaceCOLMAP.exe",
                "DensifyPointCloud.exe",
                "ReconstructMesh.exe",
                "RefineMesh.exe",
                "TextureMesh.exe",
            ):
                (openmvs_bin / name).write_text("stub")

            frames = root / "frames"
            frames.mkdir()
            sparse = root / "sparse"
            sparse.mkdir()
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (sparse / name).write_bytes(b"model")

            colmap_dir = root / "mvs_colmap"
            undistorted = colmap_dir / "undistorted"
            (undistorted / "sparse").mkdir(parents=True)
            (undistorted / "images").mkdir()
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (undistorted / "sparse" / name).write_bytes(b"model")
            (undistorted / "images" / "frame_0001.jpg").write_bytes(b"image")

            openmvs = root / "openmvs"
            openmvs.mkdir()
            (openmvs / "scene.mvs").write_bytes(b"scene")
            (openmvs / "scene_dense.mvs").write_bytes(b"dense")
            (openmvs / "scene_dense.ply").write_bytes(b"x" * 2048)
            (openmvs / "scene_mesh.ply").write_bytes(b"x" * 2048)
            (openmvs / "scene_refined.ply").write_bytes(b"x" * 2048)
            (openmvs / "object.obj").write_bytes(b"obj")
            (openmvs / "object.mtl").write_bytes(b"mtl")
            (openmvs / "object_material_00_map_Kd.jpg").write_bytes(b"texture")
            (openmvs / "texture_recipe.json").write_text(
                '{"version":"openmvs-2.4.0-seam-leveling-off-v1"}',
                encoding="utf-8",
            )

            with patch(
                "pipeline.openmvs._run_colmap",
                side_effect=AssertionError("cached undistorter must not rerun"),
            ), patch(
                "pipeline.openmvs._run_process",
                side_effect=AssertionError("cached OpenMVS stage must not rerun"),
            ):
                result = run_mesh_pipeline(
                    colmap_path=colmap_path,
                    openmvs_bin=openmvs_bin,
                    frames_dir=frames,
                    sparse_model=sparse,
                    colmap_dir=colmap_dir,
                    openmvs_dir=openmvs,
                    logs_dir=root / "logs",
                    overwrite=False,
                )

            self.assertEqual(Path(result["obj"]), openmvs / "object.obj")
            self.assertEqual(len(result["textures"]), 1)



if __name__ == "__main__":
    unittest.main()

class TestMeshRecipeProfile(unittest.TestCase):
    def test_profile_changes_undistort_dense_and_refine_arguments(self):
        from pipeline.openmvs import normalize_mesh_profile
        profile = normalize_mesh_profile({
            "undistort_max_image_size": 1600,
            "dense_resolution_level": 1,
            "dense_number_views": 6,
            "dense_max_threads": 4,
            "refine_resolution_level": 2,
        })
        undistort = build_image_undistorter_args("frames", "sparse", "undist", profile=profile)
        self.assertEqual(undistort[undistort.index("--max_image_size") + 1], "1600")
        dense = build_densify_args(Path("openmvs"), profile=profile)
        self.assertEqual(dense[dense.index("--resolution-level") + 1], "1")
        self.assertEqual(dense[dense.index("--number-views") + 1], "6")
        self.assertEqual(dense[dense.index("--max-threads") + 1], "4")
        refine = build_refine_mesh_args(Path("openmvs"), profile=profile)
        self.assertEqual(refine[refine.index("--resolution-level") + 1], "2")

    def test_auto_dense_values_omit_number_views_and_threads(self):
        from pipeline.openmvs import normalize_mesh_profile
        profile = normalize_mesh_profile({"dense_number_views": 0, "dense_max_threads": 0})
        dense = build_densify_args(Path("openmvs"), profile=profile)
        self.assertNotIn("--number-views", dense)
        self.assertNotIn("--max-threads", dense)

    def test_recipe_change_boundary_is_earliest_affected_stage(self):
        from pipeline.openmvs import DEFAULT_MESH_PROFILE, mesh_recipe_change_stage
        base = dict(DEFAULT_MESH_PROFILE)
        self.assertIsNone(mesh_recipe_change_stage(base, dict(base)))
        changed = dict(base); changed["refine_resolution_level"] = 2
        self.assertEqual(mesh_recipe_change_stage(base, changed), "refine")
        changed = dict(base); changed["dense_resolution_level"] = 1
        self.assertEqual(mesh_recipe_change_stage(base, changed), "dense")
        changed = dict(base); changed["undistort_max_image_size"] = 1600
        self.assertEqual(mesh_recipe_change_stage(base, changed), "interface")

class TestMeshRecipeInvalidation(unittest.TestCase):
    def _seed(self, root):
        import json
        from pipeline.openmvs import TEXTURE_RECIPE_VERSION, write_mesh_recipe, DEFAULT_MESH_PROFILE
        undist = root / "mvs_colmap" / "undistorted"
        sparse = undist / "sparse"; images = undist / "images"
        sparse.mkdir(parents=True); images.mkdir(parents=True)
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            (sparse / name).write_bytes(b"x")
        (images / "frame_0001.jpg").write_bytes(b"x")
        om = root / "openmvs"; om.mkdir()
        for name, size in (
            ("scene.mvs", 1), ("scene_dense.mvs", 1), ("scene_dense.ply", 2048),
            ("scene_mesh.ply", 2048), ("scene_refined.ply", 2048),
            ("object.obj", 10), ("object.mtl", 10), ("object_material_00_map_Kd.jpg", 10),
        ):
            (om / name).write_bytes(b"x" * size)
        (om / "texture_recipe.json").write_text(json.dumps({"version": TEXTURE_RECIPE_VERSION}), encoding="utf-8")
        write_mesh_recipe(om, DEFAULT_MESH_PROFILE)
        return undist, om

    def test_refine_change_preserves_dense_and_mesh_cache(self):
        import tempfile
        from pipeline.openmvs import _prepare_mesh_recipe, DEFAULT_MESH_PROFILE
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); undist, om = self._seed(root)
            desired = dict(DEFAULT_MESH_PROFILE); desired["refine_resolution_level"] = 2
            self.assertEqual(_prepare_mesh_recipe(undist, om, desired), "refine")
            self.assertTrue((om / "scene_dense.mvs").exists())
            self.assertTrue((om / "scene_mesh.ply").exists())
            self.assertFalse((om / "scene_refined.ply").exists())
            self.assertFalse((om / "object.obj").exists())

    def test_dense_change_preserves_undistort_and_scene_but_removes_dense(self):
        import tempfile
        from pipeline.openmvs import _prepare_mesh_recipe, DEFAULT_MESH_PROFILE
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); undist, om = self._seed(root)
            desired = dict(DEFAULT_MESH_PROFILE); desired["dense_number_views"] = 6
            self.assertEqual(_prepare_mesh_recipe(undist, om, desired), "dense")
            self.assertTrue(undist.exists())
            self.assertTrue((om / "scene.mvs").exists())
            self.assertFalse((om / "scene_dense.mvs").exists())

    def test_undistort_change_removes_undistort_and_interface_cache(self):
        import tempfile
        from pipeline.openmvs import _prepare_mesh_recipe, DEFAULT_MESH_PROFILE
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); undist, om = self._seed(root)
            desired = dict(DEFAULT_MESH_PROFILE); desired["undistort_max_image_size"] = 1600
            self.assertEqual(_prepare_mesh_recipe(undist, om, desired), "interface")
            self.assertFalse(undist.exists())
            self.assertFalse((om / "scene.mvs").exists())
