"""COLMAP binary-model filtering for object-only Gaussian Splat initialization."""

import json
import math
import shutil
import struct
import zlib
from pathlib import Path


_IMAGE_HEADER = struct.Struct("<I7dI")
_POINT2D = struct.Struct("<2dq")
_POINT_HEADER = struct.Struct("<Q3d3BdQ")
_TRACK = struct.Struct("<II")


def _read_c_string(handle):
    data = bytearray()
    while True:
        b = handle.read(1)
        if not b:
            raise EOFError("Unexpected EOF while reading COLMAP image name")
        if b == b"\x00":
            return data.decode("utf-8")
        data.extend(b)


def read_images_binary(path):
    images = {}
    with Path(path).open("rb") as f:
        (count,) = struct.unpack("<Q", f.read(8))
        for _ in range(count):
            raw = f.read(_IMAGE_HEADER.size)
            if len(raw) != _IMAGE_HEADER.size:
                raise RuntimeError("Invalid COLMAP images.bin")
            values = _IMAGE_HEADER.unpack(raw)
            image_id = values[0]
            name = _read_c_string(f)
            (npoints,) = struct.unpack("<Q", f.read(8))
            points = []
            for _ in range(npoints):
                item = _POINT2D.unpack(f.read(_POINT2D.size))
                points.append([item[0], item[1], item[2]])
            images[image_id] = {
                "image_id": image_id,
                "qvec": tuple(values[1:5]),
                "tvec": tuple(values[5:8]),
                "camera_id": values[8],
                "name": name,
                "points2D": points,
            }
    return images


def write_images_binary(path, images):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(struct.pack("<Q", len(images)))
        for image_id in sorted(images):
            image = images[image_id]
            f.write(_IMAGE_HEADER.pack(
                int(image_id), *image["qvec"], *image["tvec"], int(image["camera_id"])
            ))
            f.write(image["name"].encode("utf-8") + b"\x00")
            points = image["points2D"]
            f.write(struct.pack("<Q", len(points)))
            for x, y, point3d_id in points:
                f.write(_POINT2D.pack(float(x), float(y), int(point3d_id)))


def read_points3d_binary(path):
    points = {}
    with Path(path).open("rb") as f:
        (count,) = struct.unpack("<Q", f.read(8))
        for _ in range(count):
            raw = f.read(_POINT_HEADER.size)
            if len(raw) != _POINT_HEADER.size:
                raise RuntimeError("Invalid COLMAP points3D.bin")
            vals = _POINT_HEADER.unpack(raw)
            track_len = vals[-1]
            track = []
            for _ in range(track_len):
                track.append(_TRACK.unpack(f.read(_TRACK.size)))
            points[vals[0]] = {
                "point3D_id": vals[0],
                "xyz": tuple(vals[1:4]),
                "rgb": tuple(vals[4:7]),
                "error": vals[7],
                "track": track,
            }
    return points


def write_points3d_binary(path, points):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(struct.pack("<Q", len(points)))
        for point_id in sorted(points):
            point = points[point_id]
            track = point["track"]
            f.write(_POINT_HEADER.pack(
                int(point_id), *point["xyz"], *point["rgb"], float(point["error"]), len(track)
            ))
            for image_id, point2d_idx in track:
                f.write(_TRACK.pack(int(image_id), int(point2d_idx)))


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a); pb = abs(p - b); pc = abs(p - c)
    if pa <= pb and pa <= pc: return a
    if pb <= pc: return b
    return c


def read_png_u8(path):
    """Read an 8-bit non-interlaced PNG using only stdlib.

    Returns (width, height, channels, raw_unfiltered_bytes). Supports grayscale,
    grayscale+alpha, RGB and RGBA, which covers OpenCV-written SAM2 masks.
    """
    data = Path(path).read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Not a PNG file: {}".format(path))
    pos = 8; idat = bytearray(); width = height = bit_depth = color_type = interlace = None
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        kind = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or interlace != 0:
        raise RuntimeError("Unsupported mask PNG encoding: bit_depth={}, interlace={}".format(bit_depth, interlace))
    channels_by_type = {0: 1, 2: 3, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise RuntimeError("Unsupported mask PNG color type: {}".format(color_type))
    channels = channels_by_type[color_type]
    decompressed = zlib.decompress(bytes(idat))
    stride = width * channels
    expected = height * (stride + 1)
    if len(decompressed) != expected:
        raise RuntimeError("Unexpected mask PNG payload size for {}".format(path))
    out = bytearray(height * stride)
    prev = bytearray(stride)
    src = 0
    for row in range(height):
        filter_type = decompressed[src]; src += 1
        scan = bytearray(decompressed[src:src+stride]); src += stride
        for i in range(stride):
            left = scan[i-channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i-channels] if i >= channels else 0
            if filter_type == 1: scan[i] = (scan[i] + left) & 0xFF
            elif filter_type == 2: scan[i] = (scan[i] + up) & 0xFF
            elif filter_type == 3: scan[i] = (scan[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4: scan[i] = (scan[i] + _paeth(left, up, up_left)) & 0xFF
            elif filter_type != 0: raise RuntimeError("Unsupported PNG filter {}".format(filter_type))
        start = row * stride
        out[start:start+stride] = scan
        prev = scan
    return int(width), int(height), channels, bytes(out)


def _mask_foreground(mask, x, y, threshold=128):
    width, height, channels, pixels = mask
    xi = int(round(float(x))); yi = int(round(float(y)))
    if xi < 0 or yi < 0 or xi >= width or yi >= height:
        return None
    idx = (yi * width + xi) * channels
    # SAM2 masks are grayscale. For RGB/RGBA masks the first channel is enough.
    return pixels[idx] >= threshold


def filter_colmap_points_by_masks(
    source_model,
    masks_dir,
    output_model,
    report_path,
    foreground_ratio=0.60,
    min_foreground_observations=2,
    min_kept_points=1,
):
    source_model = Path(source_model); masks_dir = Path(masks_dir); output_model = Path(output_model)
    foreground_ratio = float(foreground_ratio)
    min_foreground_observations = int(min_foreground_observations)
    min_kept_points = int(min_kept_points)
    if not (0.0 < foreground_ratio <= 1.0):
        raise ValueError("foreground_ratio must be in (0, 1]")
    if min_foreground_observations <= 0:
        raise ValueError("min_foreground_observations must be > 0")
    required = [source_model / name for name in ("cameras.bin", "images.bin", "points3D.bin")]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Object sparse filter missing COLMAP files: {}".format(", ".join(missing)))

    images = read_images_binary(source_model / "images.bin")
    points = read_points3d_binary(source_model / "points3D.bin")
    mask_cache = {}
    missing_masks = set()

    def mask_for(image):
        name = image["name"]
        if name in mask_cache: return mask_cache[name]
        path = masks_dir / (name + ".png")
        if not path.exists():
            missing_masks.add(name); return None
        mask_cache[name] = read_png_u8(path)
        return mask_cache[name]

    kept = {}
    point_stats = {}
    for point_id, point in points.items():
        valid = 0; foreground = 0
        for image_id, point2d_idx in point["track"]:
            image = images.get(image_id)
            if image is None or point2d_idx >= len(image["points2D"]):
                continue
            mask = mask_for(image)
            if mask is None: continue
            x, y, _ = image["points2D"][point2d_idx]
            vote = _mask_foreground(mask, x, y)
            if vote is None: continue
            valid += 1
            if vote: foreground += 1
        ratio = (foreground / valid) if valid else 0.0
        keep = foreground >= min_foreground_observations and ratio >= foreground_ratio
        point_stats[point_id] = (valid, foreground, ratio, keep)
        if keep:
            kept[point_id] = point

    if len(kept) < min_kept_points:
        raise RuntimeError(
            "Object-only sparse filter kept only {} / {} points (< {}). "
            "Check masks or relax --foreground-ratio / --min-foreground-observations."
            .format(len(kept), len(points), min_kept_points)
        )

    kept_ids = set(kept)
    staged_images = {}
    for image_id, image in images.items():
        copy = dict(image)
        copy["points2D"] = [
            [x, y, point_id if point_id in kept_ids else -1]
            for x, y, point_id in image["points2D"]
        ]
        staged_images[image_id] = copy

    output_model.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_model / "cameras.bin", output_model / "cameras.bin")
    write_images_binary(output_model / "images.bin", staged_images)
    write_points3d_binary(output_model / "points3D.bin", kept)

    ratios = [item[2] for item in point_stats.values() if item[0] > 0]
    report = {
        "source_model": str(source_model),
        "output_model": str(output_model),
        "registered_images": len(images),
        "source_points": len(points),
        "kept_points": len(kept),
        "removed_points": len(points) - len(kept),
        "keep_ratio": (len(kept) / len(points)) if points else 0.0,
        "foreground_ratio_threshold": foreground_ratio,
        "min_foreground_observations": min_foreground_observations,
        "missing_mask_images": sorted(missing_masks),
        "mean_foreground_ratio": (sum(ratios) / len(ratios)) if ratios else 0.0,
    }
    report_path = Path(report_path); report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
