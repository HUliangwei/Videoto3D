import unittest
from pathlib import Path

import app
from pipeline.cli_commands import parse_cli_args


class TestV08CLI(unittest.TestCase):
    def test_run_commands_require_run_id(self):
        parsed = parse_cli_args(["run", "sparse", "--run", "teddy_001"])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["key"], "run.sparse")
        self.assertEqual(parsed["options"]["run"], "teddy_001")

        missing = parse_cli_args(["run", "sparse"])
        self.assertEqual(missing["kind"], "error")
        self.assertIn("--run", missing["message"])

    def test_extract_requires_input(self):
        parsed = parse_cli_args([
            "run", "extract", "--run", "teddy_001",
            "--input", r"D:\Videos\teddy.mp4",
        ])
        self.assertEqual(parsed["key"], "run.extract")
        self.assertEqual(parsed["options"]["run"], "teddy_001")
        self.assertEqual(parsed["options"]["input"], r"D:\Videos\teddy.mp4")

        missing = parse_cli_args(["run", "extract", "--run", "teddy_001"])
        self.assertEqual(missing["kind"], "error")
        self.assertIn("--input", missing["message"])

    def test_view_mesh_and_glb_accept_run_or_path(self):
        by_run = parse_cli_args(["view", "glb", "--run", "teddy_001"])
        self.assertEqual(by_run["options"]["run"], "teddy_001")

        by_path = parse_cli_args(["view", "glb", "--path", r"D:\Models\x.glb"])
        self.assertEqual(by_path["options"]["path"], r"D:\Models\x.glb")

        both = parse_cli_args([
            "view", "glb", "--run", "teddy_001", "--path", r"D:\Models\x.glb"
        ])
        self.assertEqual(both["kind"], "error")

    def test_view_masks_and_sparse_require_run(self):
        self.assertEqual(
            parse_cli_args(["view", "masks", "--run", "teddy_001"])["key"],
            "view.masks",
        )
        self.assertEqual(parse_cli_args(["view", "masks"])["kind"], "error")

    def test_glb_output_options(self):
        parsed = parse_cli_args([
            "run", "glb", "--run", "teddy_001", "--output-name", "teddy.glb"
        ])
        self.assertEqual(parsed["options"]["output_name"], "teddy.glb")

        parsed = parse_cli_args([
            "run", "glb", "--run", "teddy_001", "--output", r"D:\Models\teddy.glb"
        ])
        self.assertEqual(parsed["options"]["output"], r"D:\Models\teddy.glb")

    def test_runs_list_and_show_parse(self):
        self.assertEqual(parse_cli_args(["runs", "list"])["key"], "runs.list")
        shown = parse_cli_args(["runs", "show", "teddy_001"])
        self.assertEqual(shown["key"], "runs.show")
        self.assertEqual(shown["options"]["run"], "teddy_001")

    def test_fixed_v07_workspace_names_are_not_production_roots(self):
        root = app.resolve_run_root("teddy_001")
        self.assertEqual(root.name, "teddy_001")
        self.assertNotIn("v0_object", str(root))


if __name__ == "__main__":
    unittest.main()
