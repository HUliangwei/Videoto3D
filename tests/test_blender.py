import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.blender import build_blender_glb_command, build_blender_view_command, launch_asset_viewer


class TestBlenderPipeline(unittest.TestCase):

    def test_blender_command_runs_background_factory_startup(self):
        command = build_blender_glb_command(
            blender_path=Path("blender.exe"),
            script_path=Path("scripts/blender_export_glb.py"),
            input_obj=Path("openmvs/object.obj"),
            output_glb=Path("output/object.glb"),
        )

        self.assertEqual(
            command[0],
            str(Path("blender.exe")),
        )
        self.assertIn(
            "--background",
            command,
        )
        self.assertIn(
            "--factory-startup",
            command,
        )
        self.assertIn(
            "--python",
            command,
        )

    def test_blender_command_passes_obj_and_glb_paths_after_separator(self):
        input_obj = Path("openmvs/object.obj")
        output_glb = Path("output/object.glb")

        command = build_blender_glb_command(
            blender_path=Path("blender.exe"),
            script_path=Path("scripts/blender_export_glb.py"),
            input_obj=input_obj,
            output_glb=output_glb,
        )

        separator = command.index("--")

        script_args = command[
            separator + 1:
        ]

        self.assertIn(
            "--input",
            script_args,
        )
        self.assertIn(
            str(input_obj),
            script_args,
        )
        self.assertIn(
            "--output",
            script_args,
        )
        self.assertIn(
            str(output_glb),
            script_args,
        )


    def test_view_command_opens_gui_not_background(self):
        command = build_blender_view_command(
            blender_path=Path("blender.exe"),
            script_path=Path("scripts/blender_view_asset.py"),
            input_asset=Path("output/object.glb"),
        )

        self.assertNotIn(
            "--background",
            command,
        )
        self.assertIn(
            "--factory-startup",
            command,
        )
        self.assertIn(
            "--python",
            command,
        )

    def test_view_command_passes_asset_path(self):
        asset = Path("openmvs/object.obj")

        command = build_blender_view_command(
            blender_path=Path("blender.exe"),
            script_path=Path("scripts/blender_view_asset.py"),
            input_asset=asset,
        )

        separator = command.index("--")
        script_args = command[
            separator + 1:
        ]

        self.assertIn(
            "--input",
            script_args,
        )
        self.assertIn(
            str(asset),
            script_args,
        )



    def test_viewer_script_switches_to_material_preview(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "blender_view_asset.py"
        )

        script = script_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'space.shading.type = "MATERIAL"',
            script,
        )
        self.assertIn(
            "asset_material_stats",
            script,
        )


    def test_asset_viewer_launches_detached(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            blender = root / "blender.exe"
            script = root / "viewer.py"
            asset = root / "asset.glb"
            blender.write_bytes(b"exe")
            script.write_text("# viewer", encoding="utf-8")
            asset.write_bytes(b"glb")
            with mock.patch("pipeline.blender.launch_detached") as launch:
                launch.return_value = mock.Mock(pid=4321)
                pid = launch_asset_viewer(blender, script, asset, root)
            self.assertEqual(pid, 4321)
            launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
