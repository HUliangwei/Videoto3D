import unittest
from pipeline.cli_commands import parse_cli_args


class TestV10CLI(unittest.TestCase):
    def test_route_mesh_accepts_run_and_optional_input(self):
        parsed = parse_cli_args(["route", "mesh", "--run", "teddy_001"])
        self.assertEqual(parsed["key"], "route.mesh")
        parsed = parse_cli_args(["route", "mesh", "--run", "teddy_002", "--input", "teddy.mp4"])
        self.assertEqual(parsed["options"]["input"], "teddy.mp4")

    def test_route_splat_accepts_training_and_object_filter_overrides(self):
        parsed = parse_cli_args([
            "route", "splat", "--run", "teddy_001",
            "--steps", "10000", "--max-splats", "1000000", "--max-resolution", "960",
            "--foreground-ratio", "0.7", "--min-foreground-observations", "3",
        ])
        self.assertEqual(parsed["key"], "route.splat")
        self.assertEqual(parsed["options"]["foreground_ratio"], "0.7")
        self.assertEqual(parsed["options"]["min_foreground_observations"], "3")

    def test_run_splat_accepts_object_filter_overrides(self):
        parsed = parse_cli_args([
            "run", "splat", "--run", "teddy_001",
            "--foreground-ratio", "0.6", "--min-foreground-observations", "2",
        ])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["key"], "run.splat")

    def test_object_filter_values_are_validated(self):
        for argv in (
            ["run", "splat", "--run", "x", "--foreground-ratio", "1.2"],
            ["run", "splat", "--run", "x", "--foreground-ratio", "bad"],
            ["run", "splat", "--run", "x", "--min-foreground-observations", "0"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(parse_cli_args(argv)["kind"], "error")

    def test_view_splat_init_requires_run(self):
        self.assertEqual(parse_cli_args(["view", "splat-init"])["kind"], "error")
        parsed = parse_cli_args(["view", "splat-init", "--run", "teddy_001"])
        self.assertEqual(parsed["key"], "view.splat-init")


if __name__ == "__main__":
    unittest.main()

class TestV10RouteOrchestration(unittest.TestCase):
    def test_new_route_requires_input_when_run_does_not_exist(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        with tempfile.TemporaryDirectory() as d, patch.object(app, "WORKSPACE", Path(d) / "workspace"):
            with self.assertRaises(RuntimeError):
                app.run_route_mesh({"run": "new_001"})

    def test_mesh_route_skips_completed_shared_and_mesh_work(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        from pipeline.run_workspace import create_or_load_run, update_shared_stage, update_route_stage
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            for stage in ("extract", "mask", "sparse"):
                update_shared_stage(root, stage, "ready")
            for stage in ("dense", "reconstruct", "refine", "texture", "glb"):
                update_route_stage(root, "mesh", stage, "ready", **({"path": "output/teddy_001.glb"} if stage == "glb" else {}))
            (root / "mesh" / "openmvs").mkdir(parents=True, exist_ok=True)
            (root / "mesh" / "openmvs" / "object.obj").write_bytes(b"obj")
            (root / "output" / "teddy_001.glb").write_bytes(b"glb")
            with patch.object(app, "WORKSPACE", workspace), patch("app.run_mesh") as mesh, patch("app.run_glb") as glb, patch("app.check_required_tools") as tools:
                self.assertEqual(app.run_route_mesh({"run": "teddy_001"}), 0)
            mesh.assert_not_called(); glb.assert_not_called(); tools.assert_not_called()

    def test_splat_route_reuses_shared_and_runs_only_splat_branch(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        from pipeline.run_workspace import create_or_load_run, update_shared_stage
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"
            root, _ = create_or_load_run(workspace / "runs", "teddy_001")
            for stage in ("extract", "mask", "sparse"):
                update_shared_stage(root, stage, "ready")
            def fake_train(resolved, options):
                raw = root / "splat" / "raw" / "teddy_001_raw.ply"; raw.parent.mkdir(parents=True, exist_ok=True); raw.write_bytes(b"raw")
                from pipeline.run_workspace import update_route_stage
                update_route_stage(root, "splat", "training", "ready", steps=int(options["steps"]), max_splats=2000000, max_resolution=1280, foreground_ratio=0.6, min_foreground_observations=2, raw_path="splat/raw/teddy_001_raw.ply")
                return {}
            with patch.object(app, "WORKSPACE", workspace), patch("app._route_toolset", return_value={"brush": Path("brush.exe")}), patch("app.run_splat_training", side_effect=fake_train) as train, patch("app.run_splat_cleanup", return_value=0) as clean:
                self.assertEqual(app.run_route_splat({"run": "teddy_001", "steps": "10000"}), 0)
            self.assertEqual(train.call_args.args[1]["steps"], "10000")
            clean.assert_called_once()


class TestV11SplatRecipeResume(unittest.TestCase):
    def _ready_shared(self, workspace):
        from pipeline.run_workspace import create_or_load_run, update_shared_stage
        root, _ = create_or_load_run(workspace / "runs", "teddy_001")
        for stage in ("extract", "mask", "sparse"):
            update_shared_stage(root, stage, "ready")
        return root

    def test_route_splat_retrains_when_existing_training_recipe_differs(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        from pipeline.run_workspace import update_route_stage
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"; root = self._ready_shared(workspace)
            raw = root / "splat" / "raw" / "teddy_001_raw.ply"; raw.parent.mkdir(parents=True, exist_ok=True); raw.write_bytes(b"raw")
            update_route_stage(root, "splat", "training", "ready", steps=10000, max_splats=1000000, max_resolution=960, foreground_ratio=0.6, min_foreground_observations=2, raw_path="splat/raw/teddy_001_raw.ply")
            with patch.object(app, "WORKSPACE", workspace), patch("app._route_toolset", return_value={"brush": Path("brush.exe")}), patch("app.run_splat_training", return_value={}) as train, patch("app.run_splat_cleanup", return_value=0):
                app.run_route_splat({"run": "teddy_001"})
            train.assert_called_once()
            self.assertEqual(train.call_args.args[1]["steps"], "30000")

    def test_route_splat_skips_training_but_reruns_cleanup_when_cleanup_recipe_differs(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        from pipeline.run_workspace import update_route_stage
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"; root = self._ready_shared(workspace)
            raw = root / "splat" / "raw" / "teddy_001_raw.ply"; raw.parent.mkdir(parents=True, exist_ok=True); raw.write_bytes(b"raw")
            final = root / "output" / "teddy_001_splat.ply"; final.write_bytes(b"final")
            update_route_stage(root, "splat", "training", "ready", steps=30000, max_splats=2000000, max_resolution=1280, foreground_ratio=0.6, min_foreground_observations=2, raw_path="splat/raw/teddy_001_raw.ply")
            update_route_stage(root, "splat", "cleanup", "ready", foreground_ratio=0.6, min_views=2)
            update_route_stage(root, "splat", "ply", "ready", path="output/teddy_001_splat.ply")
            with patch.object(app, "WORKSPACE", workspace), patch("app.run_splat_training") as train, patch("app.run_splat_cleanup", return_value=0) as clean, patch("app._route_toolset") as tools:
                app.run_route_splat({"run": "teddy_001"})
            train.assert_not_called(); tools.assert_not_called(); clean.assert_called_once()

    def test_route_splat_skips_both_when_training_and_cleanup_recipes_match(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import app
        from pipeline.run_workspace import update_route_stage
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / "workspace"; root = self._ready_shared(workspace)
            raw = root / "splat" / "raw" / "teddy_001_raw.ply"; raw.parent.mkdir(parents=True, exist_ok=True); raw.write_bytes(b"raw")
            final = root / "output" / "teddy_001_splat.ply"; final.write_bytes(b"final")
            update_route_stage(root, "splat", "training", "ready", steps=30000, max_splats=2000000, max_resolution=1280, foreground_ratio=0.6, min_foreground_observations=2, raw_path="splat/raw/teddy_001_raw.ply")
            update_route_stage(root, "splat", "cleanup", "ready", foreground_ratio=0.7, min_views=3)
            update_route_stage(root, "splat", "ply", "ready", path="output/teddy_001_splat.ply")
            with patch.object(app, "WORKSPACE", workspace), patch("app.run_splat_training") as train, patch("app.run_splat_cleanup") as clean, patch("app._route_toolset") as tools:
                app.run_route_splat({"run": "teddy_001"})
            train.assert_not_called(); clean.assert_not_called(); tools.assert_not_called()


if __name__ == "__main__":
    unittest.main()
