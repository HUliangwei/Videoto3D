
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.segmentation import (
    build_segmentation_worker_command,
    copy_frames_for_masked_run,
    xywh_to_xyxy,
    sample_qa_indices,
    validate_masks,
    build_mask_qa_viewer_command,
    prepare_openmvs_masks,
)


class TestSegmentationPipeline(unittest.TestCase):

    def test_xywh_to_xyxy(self):
        self.assertEqual(
            xywh_to_xyxy((10, 20, 100, 200)),
            (10, 20, 110, 220),
        )

    def test_worker_command_contains_runtime_and_paths(self):
        runtime = {
            "python": Path("env/python.exe"),
            "checkpoint": Path("runtime/sam2/model.pt"),
            "model_config": "configs/sam2.1/sam2.1_hiera_s.yaml",
        }

        command = build_segmentation_worker_command(
            runtime=runtime,
            worker_script=Path("scripts/sam2_mask_worker.py"),
            frames_dir=Path("frames"),
            masks_dir=Path("masks"),
            report_path=Path("segmentation/report.json"),
        )

        self.assertEqual(command[0], str(runtime["python"]))
        self.assertIn("--frames", command)
        self.assertIn(str(Path("frames")), command)
        self.assertIn("--checkpoint", command)
        self.assertIn(str(runtime["checkpoint"]), command)
        self.assertIn("--model-config", command)
        self.assertIn(runtime["model_config"], command)

    def test_copy_frames_preserves_source_and_creates_target(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            original = source / "frame_0001.jpg"
            original.write_bytes(b"jpeg")

            count = copy_frames_for_masked_run(source, target)

            self.assertEqual(count, 1)
            self.assertTrue(original.exists())
            self.assertEqual(
                (target / "frame_0001.jpg").read_bytes(),
                b"jpeg",
            )

    def test_sample_qa_indices_cover_first_quarters_and_last(self):
        self.assertEqual(
            sample_qa_indices(120),
            [0, 30, 60, 89, 119],
        )

    def test_validate_masks_accepts_matching_binary_masks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            frames = root / "frames"
            masks = root / "masks"
            frames.mkdir()
            masks.mkdir()

            for index in range(1, 3):
                frame = Image.new("RGB", (8, 6), (20, 30, 40))
                frame.save(frames / f"frame_{index:04d}.jpg")
                mask = Image.new("L", (8, 6), 0)
                for x in range(2, 6):
                    for y in range(1, 5):
                        mask.putpixel((x, y), 255)
                mask.save(masks / f"frame_{index:04d}.jpg.png")

            result = validate_masks(frames, masks)

            self.assertEqual(result["frame_count"], 2)
            self.assertEqual(result["mask_count"], 2)
            self.assertEqual(result["dimensions"], [8, 6])

    def test_validate_masks_rejects_count_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            frames = root / "frames"
            masks = root / "masks"
            frames.mkdir()
            masks.mkdir()
            Image.new("RGB", (8, 6)).save(frames / "frame_0001.jpg")
            Image.new("RGB", (8, 6)).save(frames / "frame_0002.jpg")
            Image.new("L", (8, 6), 255).save(masks / "frame_0001.jpg.png")

            with self.assertRaisesRegex(RuntimeError, "count mismatch"):
                validate_masks(frames, masks)

    def test_validate_masks_rejects_non_binary_or_empty_mask(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            frames = root / "frames"
            masks = root / "masks"
            frames.mkdir()
            masks.mkdir()
            Image.new("RGB", (8, 6)).save(frames / "frame_0001.jpg")
            Image.new("L", (8, 6), 128).save(masks / "frame_0001.jpg.png")

            with self.assertRaisesRegex(RuntimeError, "binary"):
                validate_masks(frames, masks)

    def test_mask_qa_viewer_command_uses_segmentation_python(self):
        runtime = {"python": Path("env/python.exe")}
        command = build_mask_qa_viewer_command(
            runtime=runtime,
            viewer_script=Path("scripts/mask_qa_viewer.py"),
            frames_dir=Path("frames"),
            masks_dir=Path("masks"),
            output_path=Path("segmentation/mask_qa.jpg"),
        )

        self.assertEqual(command[0], str(runtime["python"]))
        self.assertIn("--frames", command)
        self.assertIn("--masks", command)
        self.assertIn("--output", command)


    def test_prepare_openmvs_masks_uses_required_dot_mask_png_names(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            frames = root / "frames"
            masks = root / "masks"
            staged = root / "openmvs_masks"
            frames.mkdir()
            masks.mkdir()

            Image.new("RGB", (8, 6)).save(frames / "frame_0001.jpg")
            Image.new("L", (8, 6), 255).save(masks / "frame_0001.jpg.png")

            result = prepare_openmvs_masks(frames, masks, staged)

            self.assertEqual(result["mask_count"], 1)
            self.assertTrue((staged / "frame_0001.mask.png").exists())
            self.assertFalse((staged / "frame_0001.jpg.mask.png").exists())
            self.assertFalse((staged / "frame_0001.jpg.png").exists())


if __name__ == "__main__":
    unittest.main()
