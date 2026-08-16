import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gui.control.server.frontend import ensure_frontend, frontend_source_hash


class GuiFrontendRuntimeTests(unittest.TestCase):
    def _project(self, root):
        gui = root / "gui"
        (gui / "control" / "web" / "src").mkdir(parents=True)
        (gui / "viewer" / "src").mkdir(parents=True)
        (gui / "package.json").write_text('{"scripts":{"build":"echo build"}}', encoding="utf-8")
        (gui / "control" / "web" / "package.json").write_text('{"name":"web"}', encoding="utf-8")
        (gui / "viewer" / "package.json").write_text('{"name":"viewer"}', encoding="utf-8")
        (gui / "control" / "web" / "src" / "App.tsx").write_text("v1", encoding="utf-8")
        (gui / "viewer" / "src" / "AssetViewer.tsx").write_text("v1", encoding="utf-8")

    def test_source_hash_changes_with_viewer_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._project(root)
            first = frontend_source_hash(root)
            (root / "gui" / "viewer" / "src" / "AssetViewer.tsx").write_text("v2", encoding="utf-8")
            self.assertNotEqual(first, frontend_source_hash(root))

    def test_ensure_frontend_runs_install_and_build_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._project(root)
            calls = []
            def runner(command, **kwargs):
                calls.append(list(command))
                if "build" in command:
                    dist = root / "gui" / "control" / "web" / "dist"
                    dist.mkdir(parents=True, exist_ok=True)
                    (dist / "index.html").write_text("ok", encoding="utf-8")
                return mock.Mock(returncode=0)
            ensure_frontend(root, npm_path="npm.cmd", runner=runner)
            self.assertEqual(calls[0][1], "install")
            self.assertEqual(calls[1][1:3], ["run", "build"])
            marker = root / "gui" / "control" / "web" / "dist" / ".videoto3d-build.json"
            self.assertTrue(json.loads(marker.read_text(encoding="utf-8"))["ready"])

    def test_ready_frontend_skips_npm(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._project(root)
            dist = root / "gui" / "control" / "web" / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("ok", encoding="utf-8")
            (dist / ".videoto3d-build.json").write_text(json.dumps({"ready": True, "source_hash": frontend_source_hash(root)}), encoding="utf-8")
            runner = mock.Mock()
            ensure_frontend(root, npm_path="npm.cmd", runner=runner)
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
