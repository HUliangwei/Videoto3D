import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

try:
    from pipeline.colmap_object import (
        filter_colmap_points_by_masks,
        read_images_binary,
        read_points3d_binary,
    )
except ImportError:
    filter_colmap_points_by_masks = None
    read_images_binary = None
    read_points3d_binary = None


def _write_png_gray(path, rows):
    height = len(rows)
    width = len(rows[0])
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def _write_images(path):
    # Two registered images. point 1 samples foreground at (1,1); point 2 samples background at (0,0).
    with Path(path).open("wb") as f:
        f.write(struct.pack("<Q", 2))
        for image_id, name in ((1, "frame_0001.jpg"), (2, "frame_0002.jpg")):
            f.write(struct.pack("<I", image_id))
            f.write(struct.pack("<7d", 1.0, 0, 0, 0, 0, 0, 0))
            f.write(struct.pack("<I", 1))
            f.write(name.encode("utf-8") + b"\x00")
            f.write(struct.pack("<Q", 2))
            f.write(struct.pack("<2dq", 1.0, 1.0, 1))
            f.write(struct.pack("<2dq", 0.0, 0.0, 2))


def _write_points(path):
    with Path(path).open("wb") as f:
        f.write(struct.pack("<Q", 2))
        for point_id, rgb in ((1, (200, 100, 50)), (2, (10, 20, 30))):
            f.write(struct.pack("<Q", point_id))
            f.write(struct.pack("<3d", float(point_id), 0.0, 0.0))
            f.write(struct.pack("<3B", *rgb))
            f.write(struct.pack("<d", 0.5))
            f.write(struct.pack("<Q", 2))
            f.write(struct.pack("<II", 1, point_id - 1))
            f.write(struct.pack("<II", 2, point_id - 1))


class TestObjectSparseFilter(unittest.TestCase):
    def test_filters_points_by_multiview_masks_and_keeps_cameras(self):
        self.assertIsNotNone(filter_colmap_points_by_masks)
        if filter_colmap_points_by_masks is None:
            return
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "src"
            dst = root / "dst"
            masks = root / "masks"
            src.mkdir(); masks.mkdir()
            (src / "cameras.bin").write_bytes(b"camera-bytes")
            _write_images(src / "images.bin")
            _write_points(src / "points3D.bin")
            _write_png_gray(masks / "frame_0001.jpg.png", [[0, 0], [0, 255]])
            _write_png_gray(masks / "frame_0002.jpg.png", [[0, 0], [0, 255]])

            report = filter_colmap_points_by_masks(
                source_model=src,
                masks_dir=masks,
                output_model=dst,
                report_path=root / "report.json",
                foreground_ratio=0.6,
                min_foreground_observations=2,
            )

            self.assertEqual((dst / "cameras.bin").read_bytes(), b"camera-bytes")
            points = read_points3d_binary(dst / "points3D.bin")
            self.assertEqual(set(points), {1})
            images = read_images_binary(dst / "images.bin")
            self.assertEqual(images[1]["points2D"][0][2], 1)
            self.assertEqual(images[1]["points2D"][1][2], -1)
            self.assertEqual(report["source_points"], 2)
            self.assertEqual(report["kept_points"], 1)
            self.assertEqual(report["removed_points"], 1)
            self.assertEqual(report["registered_images"], 2)
            saved = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["foreground_ratio_threshold"], 0.6)

    def test_rejects_filter_that_keeps_too_few_points_when_minimum_requested(self):
        self.assertIsNotNone(filter_colmap_points_by_masks)
        if filter_colmap_points_by_masks is None:
            return
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "src"; src.mkdir()
            masks = root / "masks"; masks.mkdir()
            (src / "cameras.bin").write_bytes(b"camera")
            _write_images(src / "images.bin")
            _write_points(src / "points3D.bin")
            _write_png_gray(masks / "frame_0001.jpg.png", [[0, 0], [0, 255]])
            _write_png_gray(masks / "frame_0002.jpg.png", [[0, 0], [0, 255]])
            with self.assertRaises(RuntimeError):
                filter_colmap_points_by_masks(
                    source_model=src,
                    masks_dir=masks,
                    output_model=root / "dst",
                    report_path=root / "report.json",
                    min_kept_points=2,
                )


if __name__ == "__main__":
    unittest.main()
