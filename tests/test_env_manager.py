import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.env_manager import (
    CondaPrerequisiteError,
    EnvironmentSetupError,
    environment_prefix,
    environment_python,
    environment_status,
    ensure_environment,
    find_conda,
    recipe_hash,
    repair_environment,
)


class EnvManagerTests(unittest.TestCase):
    def test_project_local_prefixes_are_stable(self):
        root = Path(r"D:\Desktop\Videoto3D")
        self.assertEqual(environment_prefix(root, "core"), root / "env" / "core")
        self.assertEqual(environment_prefix(root, "seg"), root / "env" / "seg")
        self.assertEqual(environment_prefix(root, "gui"), root / "env" / "gui")
        self.assertEqual(environment_python(root, "gui"), root / "env" / "gui" / "python.exe")

    def test_recipe_hash_changes_when_recipe_or_extra_input_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "gui" / "control" / "server").mkdir(parents=True)
            recipe = root / "config" / "envs" / "gui.yml"
            req = root / "gui" / "control" / "server" / "requirements.txt"
            recipe.write_text("dependencies:\n  - python=3.11\n", encoding="utf-8")
            req.write_text("fastapi==1\n", encoding="utf-8")
            first = recipe_hash(root, "gui")
            req.write_text("fastapi==2\n", encoding="utf-8")
            second = recipe_hash(root, "gui")
            self.assertNotEqual(first, second)

    def test_find_conda_prefers_conda_exe_environment_variable(self):
        with tempfile.TemporaryDirectory() as td:
            conda = Path(td) / "conda.exe"
            conda.write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CONDA_EXE": str(conda)}, clear=False):
                self.assertEqual(find_conda(), conda)

    def test_find_conda_a1_failure_is_clear(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("pipeline.env_manager.shutil.which", return_value=None), mock.patch("pipeline.env_manager._common_conda_candidates", return_value=[]):
            with self.assertRaises(CondaPrerequisiteError) as ctx:
                find_conda()
        message = str(ctx.exception)
        self.assertIn("Conda", message)
        self.assertIn("Miniconda", message)
        self.assertIn("conda --version", message)
        self.assertIn("python app.py gui", message)

    def test_ensure_environment_creates_prefix_and_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "config" / "envs" / "core.yml").write_text("dependencies:\n  - python=3.11\n", encoding="utf-8")
            conda = root / "conda.exe"
            conda.write_text("", encoding="utf-8")
            calls = []

            def runner(command, **kwargs):
                calls.append((list(command), kwargs))
                prefix = environment_prefix(root, "core")
                prefix.mkdir(parents=True, exist_ok=True)
                environment_python(root, "core").write_text("", encoding="utf-8")
                return mock.Mock(returncode=0)

            python_path = ensure_environment(root, "core", conda_path=conda, runner=runner)
            self.assertEqual(python_path, environment_python(root, "core"))
            self.assertIn("env", calls[0][0])
            self.assertIn("create", calls[0][0])
            self.assertIn("-p", calls[0][0])
            self.assertIn(str(environment_prefix(root, "core")), calls[0][0])
            marker = environment_prefix(root, "core") / ".videoto3d-env.json"
            state = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(state["environment"], "core")
            self.assertTrue(state["ready"])

    def test_create_command_avoids_env_create_yes_flag_for_legacy_conda(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "config" / "envs" / "core.yml").write_text(
                "dependencies:\n  - python=3.11\n", encoding="utf-8"
            )
            conda = root / "conda.exe"
            conda.write_text("", encoding="utf-8")
            calls = []

            def runner(command, **kwargs):
                calls.append(list(command))
                prefix = environment_prefix(root, "core")
                prefix.mkdir(parents=True, exist_ok=True)
                environment_python(root, "core").write_text("", encoding="utf-8")
                return mock.Mock(returncode=0)

            ensure_environment(root, "core", conda_path=conda, runner=runner)
            create_command = calls[0]
            self.assertEqual(create_command[1:3], ["env", "create"])
            self.assertNotIn("-y", create_command)
            self.assertNotIn("--yes", create_command)

    def test_update_command_avoids_unsupported_yes_flag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "config" / "envs" / "core.yml").write_text(
                "dependencies:\n  - python=3.11\n", encoding="utf-8"
            )
            prefix = environment_prefix(root, "core")
            prefix.mkdir(parents=True)
            environment_python(root, "core").write_text("", encoding="utf-8")
            conda = root / "conda.exe"
            conda.write_text("", encoding="utf-8")
            calls = []

            def runner(command, **kwargs):
                calls.append(list(command))
                return mock.Mock(returncode=0)

            ensure_environment(root, "core", conda_path=conda, runner=runner)
            update_command = calls[0]
            self.assertEqual(update_command[1:3], ["env", "update"])
            self.assertNotIn("-y", update_command)
            self.assertNotIn("--yes", update_command)

    def test_ready_environment_skips_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "config" / "envs" / "core.yml").write_text("dependencies:\n  - python=3.11\n", encoding="utf-8")
            prefix = environment_prefix(root, "core")
            prefix.mkdir(parents=True)
            environment_python(root, "core").write_text("", encoding="utf-8")
            (prefix / ".videoto3d-env.json").write_text(json.dumps({
                "schema": 1,
                "environment": "core",
                "recipe_hash": recipe_hash(root, "core"),
                "ready": True,
            }), encoding="utf-8")
            runner = mock.Mock()
            ensure_environment(root, "core", conda_path=root / "missing-conda.exe", runner=runner)
            runner.assert_not_called()
            self.assertEqual(environment_status(root, "core")["status"], "READY")

    def test_repair_removes_only_selected_environment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config" / "envs").mkdir(parents=True)
            (root / "config" / "envs" / "gui.yml").write_text("dependencies:\n  - python=3.11\n", encoding="utf-8")
            for name in ("core", "gui", "seg"):
                p = environment_prefix(root, name)
                p.mkdir(parents=True)
                (p / "sentinel.txt").write_text(name, encoding="utf-8")
            (root / "workspace").mkdir()
            (root / "workspace" / "keep.txt").write_text("keep", encoding="utf-8")
            conda = root / "conda.exe"
            conda.write_text("", encoding="utf-8")

            def runner(command, **kwargs):
                prefix = environment_prefix(root, "gui")
                prefix.mkdir(parents=True, exist_ok=True)
                environment_python(root, "gui").write_text("", encoding="utf-8")
                return mock.Mock(returncode=0)

            repair_environment(root, "gui", conda_path=conda, runner=runner)
            self.assertTrue((environment_prefix(root, "core") / "sentinel.txt").exists())
            self.assertTrue((environment_prefix(root, "seg") / "sentinel.txt").exists())
            self.assertTrue((root / "workspace" / "keep.txt").exists())
            self.assertFalse((environment_prefix(root, "gui") / "sentinel.txt").exists())


if __name__ == "__main__":
    unittest.main()

class CoreEnvironmentRecipeTests(unittest.TestCase):
    def test_core_recipe_includes_pillow(self):
        root = Path(__file__).resolve().parents[1]
        recipe = (root / "config" / "envs" / "core.yml").read_text(encoding="utf-8").lower()
        self.assertIn("pillow", recipe)

    def test_core_health_probe_imports_pil(self):
        source = (Path(__file__).resolve().parents[1] / "pipeline" / "env_manager.py").read_text(encoding="utf-8")
        self.assertIn("from PIL import Image", source)
