import unittest
from pipeline.cli_commands import command_spec, parse_cli_args


class EnvCliTests(unittest.TestCase):
    def test_env_status_is_canonical(self):
        parsed = parse_cli_args(["env", "status"])
        self.assertEqual(parsed["key"], "env.status")
        self.assertEqual(command_spec("env.status")["command"], "python app.py env status")

    def test_env_repair_accepts_only_known_environment(self):
        parsed = parse_cli_args(["env", "repair", "gui"])
        self.assertEqual(parsed["key"], "env.repair")
        self.assertEqual(parsed["options"]["environment"], "gui")
        bad = parse_cli_args(["env", "repair", "other"])
        self.assertEqual(bad["kind"], "error")


if __name__ == "__main__":
    unittest.main()
