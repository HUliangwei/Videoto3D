import struct

from gui.control.server.artifacts import (
    colmap_camera_centers_as_ply,
    read_colmap_camera_centers,
)


def _write_images_bin(path):
    # One registered image. COLMAP quaternion order is qw,qx,qy,qz.
    with path.open("wb") as handle:
        handle.write(struct.pack("<Q", 1))
        handle.write(struct.pack(
            "<i7di",
            7,
            1.0, 0.0, 0.0, 0.0,  # identity rotation
            1.0, 2.0, 3.0,       # t
            1,
        ))
        handle.write(b"frame_0001.jpg\x00")
        handle.write(struct.pack("<Q", 0))


def test_read_colmap_camera_centers_uses_minus_rt_t(tmp_path):
    model = tmp_path / "sparse" / "0"
    model.mkdir(parents=True)
    _write_images_bin(model / "images.bin")

    centers = read_colmap_camera_centers(model)
    assert len(centers) == 1
    item = centers[0]
    assert item["image_id"] == 7
    assert item["name"] == "frame_0001.jpg"
    assert item["center"] == (-1.0, -2.0, -3.0)


def test_camera_trajectory_ply_is_browser_readable(tmp_path):
    model = tmp_path / "sparse" / "0"
    model.mkdir(parents=True)
    _write_images_bin(model / "images.bin")

    payload = colmap_camera_centers_as_ply(model)
    header, body = payload.split(b"end_header\n", 1)
    assert b"element vertex 1" in header
    assert len(body) == struct.calcsize("<fffBBB")
    x, y, z, r, g, b = struct.unpack("<fffBBB", body)
    assert (round(x, 6), round(y, 6), round(z, 6)) == (-1.0, -2.0, -3.0)
    assert (r, g, b) == (240, 164, 108)
