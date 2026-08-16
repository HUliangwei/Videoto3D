import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

from pipeline.colmap_object import write_images_binary

try:
    from pipeline.splat_cleanup import cleanup_splat, read_ply_element_counts, read_ply_vertex_count
except ModuleNotFoundError:
    cleanup_splat = read_ply_element_counts = read_ply_vertex_count = None


def write_gray_png(path, width, height, foreground_box):
    x0, y0, x1, y1 = foreground_box
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.append(255 if x0 <= x <= x1 and y0 <= y <= y1 else 0)
    payload = zlib.compress(bytes(rows))
    def chunk(kind, data):
        import binascii
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", payload)
    png += chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def write_cameras_binary(path):
    # camera_id=1, SIMPLE_PINHOLE(model_id=0), 100x100, f=50,cx=50,cy=50
    with Path(path).open("wb") as f:
        f.write(struct.pack("<Q", 1))
        f.write(struct.pack("<IiQQ", 1, 0, 100, 100))
        f.write(struct.pack("<3d", 50.0, 50.0, 50.0))


def write_test_images(path):
    images = {}
    for image_id in (1, 2, 3):
        images[image_id] = {
            "image_id": image_id,
            "qvec": (1.0, 0.0, 0.0, 0.0),
            "tvec": (0.0, 0.0, 0.0),
            "camera_id": 1,
            "name": f"frame_{image_id:04d}.jpg",
            "points2D": [],
        }
    write_images_binary(path, images)


def write_binary_splat(path):
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "element vertex 3\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property float opacity\n"
        "end_header\n"
    ).encode("ascii")
    rows = [
        (0.0, 0.0, 5.0, 0.9),   # projects to center => foreground
        (4.0, 0.0, 5.0, 0.8),   # projects x=90 => background
        (0.0, 0.0, -5.0, 0.7),  # behind camera => no valid views
    ]
    with Path(path).open("wb") as f:
        f.write(header)
        for row in rows:
            f.write(struct.pack("<4f", *row))


class TestSplatCleanup(unittest.TestCase):
    def test_binary_ply_cleanup_keeps_only_multi_view_foreground_splats(self):
        self.assertIsNotNone(cleanup_splat)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "raw.ply"; out = root / "clean.ply"; report = root / "cleanup.json"
            sparse = root / "sparse"; masks = root / "masks"
            sparse.mkdir(); masks.mkdir()
            write_binary_splat(raw); write_cameras_binary(sparse / "cameras.bin"); write_test_images(sparse / "images.bin")
            for i in (1, 2, 3):
                write_gray_png(masks / f"frame_{i:04d}.jpg.png", 100, 100, (40, 40, 60, 60))

            result = cleanup_splat(raw, out, sparse, masks, report, foreground_ratio=0.7, min_views=3, min_kept_splats=1)
            self.assertEqual(result["raw_splats"], 3)
            self.assertEqual(result["clean_splats"], 1)
            self.assertEqual(result["removed_splats"], 2)
            self.assertAlmostEqual(result["removal_ratio"], 2 / 3)
            self.assertEqual(read_ply_vertex_count(out), 1)
            self.assertEqual(read_ply_element_counts(out)["vertex"], 1)
            saved = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(saved["valid_camera_count"], 3)
            self.assertEqual(saved["foreground_ratio_threshold"], 0.7)
            self.assertEqual(saved["min_views"], 3)

    def test_cleanup_rejects_invalid_thresholds(self):
        self.assertIsNotNone(cleanup_splat)
        with self.assertRaises(ValueError):
            cleanup_splat("a", "b", "c", "d", "e", foreground_ratio=1.1)
        with self.assertRaises(ValueError):
            cleanup_splat("a", "b", "c", "d", "e", min_views=0)


if __name__ == "__main__":
    unittest.main()
