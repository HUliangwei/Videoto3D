from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from gui.control.server.launcher import gui_runtime_status, gui_python_path
from pipeline.cli_commands import command_spec, parse_cli_args


class GuiCliTests(unittest.TestCase):
    def test_gui_is_canonical_command(self):
        parsed = parse_cli_args(["gui"])
        self.assertEqual(parsed["kind"], "command")
        self.assertEqual(parsed["key"], "gui")
        self.assertEqual(command_spec("gui")["command"], "python app.py gui")

    def test_gui_runtime_requires_built_frontend(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("gui.control.server.launcher.importlib.util.find_spec", return_value=object()):
                ready, detail = gui_runtime_status(root)
            self.assertFalse(ready)
            self.assertIn("npm run build", detail)

    def test_gui_runtime_accepts_dependencies_and_dist(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            dist = root / "gui" / "control" / "web" / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("ok", encoding="utf-8")
            with mock.patch("gui.control.server.launcher.importlib.util.find_spec", return_value=object()):
                ready, detail = gui_runtime_status(root)
            self.assertTrue(ready)
            self.assertIn("ready", detail.lower())

    def test_gui_python_is_project_local(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(gui_python_path(root), root / "env" / "gui" / "python.exe")


if __name__ == "__main__":
    unittest.main()

class GuiLifecycleTests(unittest.TestCase):
    def test_ctrl_c_requests_child_shutdown_then_waits(self):
        from gui.control.server.launcher import _wait_for_gui_process

        class FakeProcess:
            def __init__(self):
                self.calls = 0
                self.terminated = False
            def wait(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise KeyboardInterrupt()
                return 0
            def poll(self):
                return None
            def terminate(self):
                self.terminated = True

        proc = FakeProcess()
        requested = []
        code = _wait_for_gui_process(proc, "http://127.0.0.1:8765", shutdown_request=lambda url: requested.append(url))
        self.assertEqual(code, 0)
        self.assertEqual(requested, ["http://127.0.0.1:8765/api/system/shutdown?force=1"])
        self.assertFalse(proc.terminated)
