import unittest
from pipeline.cli_commands import parse_cli_args


class TestV09CLI(unittest.TestCase):
    def test_run_splat_parses_run_and_profile_overrides(self):
        parsed = parse_cli_args([
            "run", "splat", "--run", "teddy_001",
            "--steps", "15000", "--max-splats", "1500000",
            "--max-resolution", "1024",
        ])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["key"], "run.splat")
        self.assertEqual(parsed["options"]["run"], "teddy_001")
        self.assertEqual(parsed["options"]["steps"], "15000")
        self.assertEqual(parsed["options"]["max_splats"], "1500000")
        self.assertEqual(parsed["options"]["max_resolution"], "1024")

    def test_run_splat_requires_run_and_positive_numeric_values(self):
        self.assertEqual(parse_cli_args(["run", "splat"])["kind"], "error")
        for option, value in (("--steps", "0"), ("--max-splats", "bad"), ("--max-resolution", "-1")):
            with self.subTest(option=option):
                parsed = parse_cli_args(["run", "splat", "--run", "teddy_001", option, value])
                self.assertEqual(parsed["kind"], "error")

    def test_view_splat_accepts_exactly_one_run_or_path(self):
        by_run = parse_cli_args(["view", "splat", "--run", "teddy_001"])
        self.assertEqual(by_run["key"], "view.splat")
        by_path = parse_cli_args(["view", "splat", "--path", r"D:\Models\teddy.ply"])
        self.assertEqual(by_path["key"], "view.splat")
        both = parse_cli_args([
            "view", "splat", "--run", "teddy_001", "--path", r"D:\Models\teddy.ply"
        ])
        self.assertEqual(both["kind"], "error")


if __name__ == "__main__":
    unittest.main()
