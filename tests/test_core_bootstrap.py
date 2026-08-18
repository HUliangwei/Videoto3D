import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bootstrap import bootstrap_core
from pipeline.env_manager import environment_python


class CoreBootstrapTests(unittest.TestCase):
    def test_outer_python_reexecs_into_project_core(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = environment_python(root, "core")
            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            calls = []
            with mock.patch("bootstrap.ensure_environment", return_value=target):
                handled = bootstrap_core(
                    root,
                    ["doctor"],
                    executable=Path(td) / "outer-python.exe",
                    execv=lambda exe, argv: calls.append((exe, argv)),
                )
            self.assertTrue(handled)
            self.assertEqual(Path(calls[0][0]), target)
            self.assertEqual(Path(calls[0][1][1]), root / "Videoto3D.py")
            self.assertEqual(calls[0][1][2:], ["doctor"])
            self.assertEqual(__import__("os").environ.get("PYTHONNOUSERSITE"), "1")

    def test_core_python_continues_without_reexec(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = environment_python(root, "core")
            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            ensure = mock.Mock()
            with mock.patch("bootstrap.ensure_environment", ensure):
                handled = bootstrap_core(root, ["doctor"], executable=target, execv=mock.Mock())
            self.assertFalse(handled)
            ensure.assert_not_called()

    def test_repair_core_is_handled_before_entering_core(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer = Path(td) / "outer.exe"
            with mock.patch("bootstrap.repair_environment") as repair:
                handled = bootstrap_core(root, ["env", "repair", "core"], executable=outer, execv=mock.Mock())
            self.assertTrue(handled)
            repair.assert_called_once_with(root, "core")


if __name__ == "__main__":
    unittest.main()
