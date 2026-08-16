import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import app
from pipeline.cli_commands import (
    canonical_command_lines,
    command_spec,
    parse_cli_args,
    print_command_annotation,
)
from pipeline.run_workspace import create_or_load_run


class TestCanonicalCLI(unittest.TestCase):
    def test_canonical_commands_parse_with_v08_scoping(self):
        cases = {
            ("doctor",): "doctor",
            ("run", "extract", "--run", "x", "--input", "video.mp4"): "run.extract",
            ("run", "mask", "--run", "x"): "run.mask",
            ("run", "sparse", "--run", "x"): "run.sparse",
            ("run", "mesh", "--run", "x"): "run.mesh",
            ("run", "glb", "--run", "x"): "run.glb",
            ("run", "splat", "--run", "x"): "run.splat",
            ("view", "masks", "--run", "x"): "view.masks",
            ("view", "sparse", "--run", "x"): "view.sparse",
            ("view", "mesh", "--run", "x"): "view.mesh",
            ("view", "glb", "--run", "x"): "view.glb",
            ("view", "splat", "--run", "x"): "view.splat",
            ("runs", "list"): "runs.list",
            ("runs", "show", "x"): "runs.show",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(parse_cli_args(list(argv))["key"], expected)

    def test_legacy_flat_commands_are_rejected_with_run_scoped_replacement(self):
        result = parse_cli_args(["sparse"])
        self.assertEqual(result["kind"], "legacy")
        self.assertEqual(result["replacement"], "python app.py run sparse --run <run_id>")

    def test_annotations_are_chinese_and_include_io_and_next_step(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            print_command_annotation(command_spec("run.mesh"), {"run": "teddy_001"})
        output = stream.getvalue()
        self.assertIn("命令：python app.py run mesh --run teddy_001", output)
        self.assertIn("说明：", output)
        self.assertIn("输入：", output)
        self.assertIn("输出：", output)
        self.assertIn("下一步：", output)
        self.assertIn("SAM2", output)
        self.assertIn("OpenMVS", output)

    def test_tool_requirements_follow_canonical_keys(self):
        self.assertEqual(app.required_tools_for_key("run.extract"), ("ffmpeg",))
        self.assertEqual(app.required_tools_for_key("run.mask"), ())
        self.assertEqual(app.required_tools_for_key("view.masks"), ())
        self.assertEqual(app.required_tools_for_key("run.sparse"), ("colmap",))
        self.assertEqual(app.required_tools_for_key("run.mesh"), ("colmap", "openmvs"))
        self.assertEqual(app.required_tools_for_key("run.glb"), ("blender",))
        self.assertEqual(app.required_tools_for_key("run.splat"), ("brush",))
        self.assertEqual(app.required_tools_for_key("view.splat"), ("brush",))
        self.assertEqual(app.required_tools_for_key("runs.list"), ())

    def test_different_run_ids_resolve_to_isolated_roots(self):
        teddy = app.resolve_run_root("teddy_001")
        cup = app.resolve_run_root("cup_001")
        self.assertNotEqual(teddy, cup)
        self.assertEqual(teddy.name, "teddy_001")
        self.assertEqual(cup.name, "cup_001")

    def test_readme_contains_every_canonical_command(self):
        text = Path("README.md").read_text(encoding="utf-8")
        for command in canonical_command_lines():
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_extract_invalidation_only_clears_same_run_downstream(self):
        with tempfile.TemporaryDirectory() as d:
            runs = Path(d) / "runs"
            teddy, _ = create_or_load_run(runs, "teddy_001")
            cup, _ = create_or_load_run(runs, "cup_001")
            (teddy / "frames" / "frame_0001.jpg").write_bytes(b"rgb")
            (teddy / "colmap" / "database.db").write_bytes(b"old")
            (teddy / "masks" / "frame_0001.jpg.png").write_bytes(b"old")
            (cup / "colmap" / "database.db").write_bytes(b"cup")

            app.invalidate_after_extract(teddy)

            self.assertTrue((teddy / "frames" / "frame_0001.jpg").exists())
            self.assertFalse((teddy / "colmap" / "database.db").exists())
            self.assertFalse((teddy / "masks" / "frame_0001.jpg.png").exists())
            self.assertTrue((cup / "colmap" / "database.db").exists())

    def test_sparse_uses_selected_run_and_records_manifest(self):
        fake_result = {
            "frame_count": 120,
            "database": "database.db",
            "model": "sparse/0",
            "model_count": 1,
            "stats": {
                "registered_images": 114,
                "points3D": 6537,
                "mean_track_length": 5.4,
                "mean_reprojection_error": 0.91,
            },
            "logs": {"model_analyzer": "analyzer.log"},
        }
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            run_root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            with patch.object(app, "WORKSPACE", workspace), patch(
                "app.run_sparse_reconstruction", return_value=fake_result
            ) as sparse:
                code = app.run_sparse(
                    {"colmap": Path("COLMAP.bat")},
                    {"run": "teddy_001"},
                )
            self.assertEqual(code, 0)
            self.assertEqual(sparse.call_args.kwargs["frames_dir"], run_root / "frames")
            manifest = (run_root / "run.json").read_text(encoding="utf-8")
            self.assertIn('"registered_images": 114', manifest)

    def test_splat_uses_selected_run_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            run_root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            with patch.object(app, "WORKSPACE", workspace), patch(
                "app.run_splat_training", return_value={"raw_ply": str(run_root / "splat" / "raw" / "teddy_001_raw.ply")}
            ) as train, patch("app.run_splat_cleanup", return_value=0) as clean:
                code = app.run_splat(
                    {"brush": Path("brush.exe")},
                    {"run": "teddy_001", "steps": "30000", "max_splats": "2000000", "max_resolution": "1280"},
                )
            self.assertEqual(code, 0)
            self.assertEqual(train.call_args.args[1]["run"], "teddy_001")
            clean.assert_called_once()

    def test_view_splat_resolves_manifest_output(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            run_root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            output = run_root / "output" / "teddy_001_splat.ply"
            output.write_bytes(b"ply")
            from pipeline.run_workspace import update_run_stage
            update_run_stage(run_root, "splat", "ready", path="output/teddy_001_splat.ply")
            with patch.object(app, "WORKSPACE", workspace), patch(
                "app.launch_brush_viewer", return_value=7777
            ) as viewer:
                code = app.run_view_splat({"brush": Path("brush.exe")}, {"run": "teddy_001"})
            self.assertEqual(code, 0)
            self.assertEqual(viewer.call_args.kwargs["splat_path"], output)

    def test_mesh_completion_does_not_delete_existing_splat_output(self):
        fake_mesh = {
            "obj": "openmvs/object.obj",
            "mtl": "openmvs/object.mtl",
            "dense_ply": "openmvs/scene_dense.ply",
            "refined_ply": "openmvs/scene_refined.ply",
            "textures": [],
        }
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            run_root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            (run_root / "frames" / "frame_0001.jpg").write_bytes(b"rgb")
            (run_root / "masks" / "frame_0001.jpg.png").write_bytes(b"mask")
            # Avoid real mask validation/staging and OpenMVS execution.
            splat = run_root / "output" / "teddy_001_splat.ply"
            splat.write_bytes(b"ply")
            from pipeline.run_workspace import update_run_stage
            update_run_stage(run_root, "splat", "ready", path="output/teddy_001_splat.ply")
            with patch.object(app, "WORKSPACE", workspace), \
                 patch("app.validate_masks", return_value={"frame_count": 1, "mask_count": 1}), \
                 patch("app.prepare_openmvs_masks", return_value={"output_dir": run_root / "openmvs_masks"}), \
                 patch("app.run_mesh_pipeline", return_value=fake_mesh):
                code = app.run_mesh({"colmap": Path("COLMAP.bat"), "openmvs": Path("openmvs")}, {"run": "teddy_001"})
            self.assertEqual(code, 0)
            self.assertTrue(splat.exists())


if __name__ == "__main__":
    unittest.main()
