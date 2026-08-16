import unittest

from app import openmvs_help_exit_code_is_valid


class TestOpenMVSDoctorRules(unittest.TestCase):

    def test_help_exit_code_zero_is_valid(self):
        self.assertTrue(
            openmvs_help_exit_code_is_valid(0)
        )

    def test_help_exit_code_one_is_valid(self):
        self.assertTrue(
            openmvs_help_exit_code_is_valid(1)
        )

    def test_abnormal_exit_code_is_invalid(self):
        self.assertFalse(
            openmvs_help_exit_code_is_valid(-1073741515)
        )


import inspect
import json
import tempfile
from pathlib import Path
import sys

import app


class TestDoctorConfigAndCommandScope(unittest.TestCase):

    def test_run_tool_returns_exactly_code_and_output(self):
        result = app.run_tool(
            Path(sys.executable),
            "--version",
        )

        self.assertEqual(
            len(result),
            2,
        )


    def test_check_required_tools_resolves_requested_tool(self):
        from unittest.mock import patch

        with patch(
            "app.resolve_tool",
            return_value=(True, "C:/COLMAP/COLMAP.bat", "saved", "COLMAP test"),
        ):
            ok, resolved = app.check_required_tools(("colmap",))

        self.assertTrue(ok)
        self.assertEqual(resolved["colmap"], Path("C:/COLMAP/COLMAP.bat"))

    def test_mask_requires_no_standard_reconstruction_tools(self):
        self.assertEqual(
            app.required_tools_for_key("run.mask"),
            (),
        )

    def test_view_masks_requires_no_standard_reconstruction_tools(self):
        self.assertEqual(
            app.required_tools_for_key("view.masks"),
            (),
        )

    def test_resolve_run_root_uses_explicit_run_id(self):
        self.assertEqual(app.resolve_run_root("teddy_001").name, "teddy_001")
        self.assertEqual(app.resolve_run_root("cup_001").name, "cup_001")
        self.assertNotEqual(
            app.resolve_run_root("teddy_001"),
            app.resolve_run_root("cup_001"),
        )


    def test_view_glb_requires_only_blender(self):
        self.assertTrue(
            hasattr(
                app,
                "required_tools_for_key",
            )
        )
        self.assertEqual(
            app.required_tools_for_key("view.glb"),
            ("blender",),
        )

    def test_load_config_falls_back_to_legacy_when_primary_is_empty(self):
        self.assertIn(
            "primary_path",
            inspect.signature(
                app.load_config
            ).parameters,
        )

        if "primary_path" not in inspect.signature(
            app.load_config
        ).parameters:
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            primary = temp_dir / "tools.json"
            legacy = temp_dir / "tool.json"

            primary.write_text(
                "",
                encoding="utf-8",
            )
            legacy.write_text(
                json.dumps(
                    {
                        "tools": {
                            "blender": {
                                "path": "C:/Blender/blender.exe",
                                "source": "legacy",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            loaded = app.load_config(
                primary_path=primary,
                legacy_path=legacy,
            )

            self.assertEqual(
                loaded["tools"]["blender"]["source"],
                "legacy",
            )


if __name__ == "__main__":
    unittest.main()
