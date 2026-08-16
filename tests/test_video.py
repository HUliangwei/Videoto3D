import tempfile
import unittest
from pathlib import Path

from pipeline.video import build_ffmpeg_extract_command


class TestVideoPipeline(unittest.TestCase):

    def test_build_ffmpeg_extract_command_uses_requested_fps(self):
        command = build_ffmpeg_extract_command(
            ffmpeg_path=Path("ffmpeg.exe"),
            input_video=Path("input.mp4"),
            output_pattern=Path("frames/frame_%04d.jpg"),
            fps=4,
        )

        self.assertEqual(command[0], "ffmpeg.exe")
        self.assertIn("fps=4", command)
        self.assertIn("-q:v", command)
        self.assertEqual(
            command[-1],
            str(Path("frames/frame_%04d.jpg")),
        )

    def test_build_ffmpeg_extract_command_keeps_input_path(self):
        input_video = Path("workspace/runs/v0_object/source/object.mp4")

        command = build_ffmpeg_extract_command(
            ffmpeg_path=Path("ffmpeg.exe"),
            input_video=input_video,
            output_pattern=Path("frames/frame_%04d.jpg"),
            fps=4,
        )

        self.assertIn(str(input_video), command)


if __name__ == "__main__":
    unittest.main()
