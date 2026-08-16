
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.segmentation_runtime import (
    load_segmentation_config,
    resolve_config_paths,
    segmentation_python_path,
)


class TestSegmentationRuntime(unittest.TestCase):

    def test_missing_config_loads_empty_dict(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                load_segmentation_config(Path(d) / "missing.json"),
                {},
            )

    def test_relative_paths_are_resolved_from_project_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = {
                "python": "runtime/seg/python.exe",
                "sam2_repo": "runtime/sam2/repo",
                "checkpoint": "runtime/sam2/checkpoints/model.pt",
                "model_config": "configs/sam2.1/sam2.1_hiera_s.yaml",
            }

            resolved = resolve_config_paths(config, root)

            self.assertEqual(
                resolved["python"],
                root / "runtime/seg/python.exe",
            )
            self.assertEqual(
                resolved["checkpoint"],
                root / "runtime/sam2/checkpoints/model.pt",
            )
            self.assertEqual(
                resolved["model_config"],
                "configs/sam2.1/sam2.1_hiera_s.yaml",
            )

    def test_segmentation_python_is_project_local(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(
                segmentation_python_path(root),
                root / "env" / "seg" / "python.exe",
            )


if __name__ == "__main__":
    unittest.main()
