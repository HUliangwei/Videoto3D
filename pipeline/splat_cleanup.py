"""Post-Brush Gaussian Splat cleanup using COLMAP cameras + existing SAM2 masks.

The cleanup is intentionally lightweight: it does not retrain Brush.  It projects
final Gaussian centers back into the original registered COLMAP views and keeps a
Gaussian only when enough valid views agree that the projected center lies inside
the SAM2 foreground mask.
"""

import json
import math
import struct
from pathlib import Path

import numpy as np

from pipeline.colmap_object import read_images_binary, read_png_u8


_CAMERA_MODEL_PARAM_COUNTS = {
    0: 3,   # SIMPLE_PINHOLE
    1: 4,   # PINHOLE
    2: 4,   # SIMPLE_RADIAL
    3: 5,   # RADIAL
    4: 8,   # OPENCV
    5: 8,   # OPENCV_FISHEYE
    6: 12,  # FULL_OPENCV
    7: 5,   # FOV
    8: 4,   # SIMPLE_RADIAL_FISHEYE
    9: 5,   # RADIAL_FISHEYE
}
_CAMERA_MODEL_NAMES = {
    0: "SIMPLE_PINHOLE", 1: "PINHOLE", 2: "SIMPLE_RADIAL", 3: "RADIAL",
    4: "OPENCV", 5: "OPENCV_FISHEYE", 6: "FULL_OPENCV", 7: "FOV",
    8: "SIMPLE_RADIAL_FISHEYE", 9: "RADIAL_FISHEYE",
}
_PLY_DTYPES = {
    "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1",
    "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
    "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4",
    "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
    "long": "<i8", "int64": "<i8", "ulong": "<u8", "uint64": "<u8",
}


def read_cameras_binary(path):
    cameras = {}
    with Path(path).open("rb") as f:
        raw = f.read(8)
        if len(raw) != 8:
            raise RuntimeError("Invalid COLMAP cameras.bin")
        (count,) = struct.unpack("<Q", raw)
        for _ in range(count):
            header = f.read(struct.calcsize("<IiQQ"))
            if len(header) != struct.calcsize("<IiQQ"):
                raise RuntimeError("Invalid COLMAP cameras.bin camera record")
            camera_id, model_id, width, height = struct.unpack("<IiQQ", header)
            nparams = _CAMERA_MODEL_PARAM_COUNTS.get(model_id)
            if nparams is None:
                raise RuntimeError(
                    "Unsupported COLMAP camera model id {} for Splat cleanup".format(model_id)
                )
            params_raw = f.read(8 * nparams)
            if len(params_raw) != 8 * nparams:
                raise RuntimeError("Invalid COLMAP cameras.bin parameter payload")
            params = struct.unpack("<{}d".format(nparams), params_raw)
            cameras[camera_id] = {
                "camera_id": camera_id,
                "model_id": model_id,
                "model_name": _CAMERA_MODEL_NAMES.get(model_id, str(model_id)),
                "width": int(width),
                "height": int(height),
                "params": params,
            }
    return cameras


def _qvec_to_rotmat(qvec):
    qw, qx, qy, qz = [float(v) for v in qvec]
    return np.asarray([
        [1 - 2*qy*qy - 2*qz*qz, 2*qx*qy - 2*qz*qw, 2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw, 1 - 2*qx*qx - 2*qz*qz, 2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw, 2*qy*qz + 2*qx*qw, 1 - 2*qx*qx - 2*qy*qy],
    ], dtype=np.float64)


def _distort(camera, x, y):
    model = camera["model_id"]
    p = camera["params"]
    if model == 0:  # SIMPLE_PINHOLE
        f, cx, cy = p
        return f*x + cx, f*y + cy
    if model == 1:  # PINHOLE
        fx, fy, cx, cy = p
        return fx*x + cx, fy*y + cy
    if model == 2:  # SIMPLE_RADIAL
        f, cx, cy, k = p
        r2 = x*x + y*y
        d = 1.0 + k*r2
        return f*(x*d) + cx, f*(y*d) + cy
    if model == 3:  # RADIAL
        f, cx, cy, k1, k2 = p
        r2 = x*x + y*y
        d = 1.0 + k1*r2 + k2*r2*r2
        return f*(x*d) + cx, f*(y*d) + cy
    if model == 4:  # OPENCV
        fx, fy, cx, cy, k1, k2, p1, p2 = p
        r2 = x*x + y*y
        radial = 1.0 + k1*r2 + k2*r2*r2
        xd = x*radial + 2*p1*x*y + p2*(r2 + 2*x*x)
        yd = y*radial + p1*(r2 + 2*y*y) + 2*p2*x*y
        return fx*xd + cx, fy*yd + cy
    if model == 6:  # FULL_OPENCV
        fx, fy, cx, cy, k1, k2, p1, p2, k3, k4, k5, k6 = p
        r2 = x*x + y*y
        num = 1 + k1*r2 + k2*r2*r2 + k3*r2*r2*r2
        den = 1 + k4*r2 + k5*r2*r2 + k6*r2*r2*r2
        radial = num / np.where(np.abs(den) < 1e-12, 1e-12, den)
        xd = x*radial + 2*p1*x*y + p2*(r2 + 2*x*x)
        yd = y*radial + p1*(r2 + 2*y*y) + 2*p2*x*y
        return fx*xd + cx, fy*yd + cy
    if model in (5, 8, 9):  # fisheye families
        if model == 5:
            fx, fy, cx, cy, k1, k2, k3, k4 = p
            coeffs = (k1, k2, k3, k4)
        elif model == 8:
            f, cx, cy, k1 = p; fx = fy = f; coeffs = (k1,)
        else:
            f, cx, cy, k1, k2 = p; fx = fy = f; coeffs = (k1, k2)
        r = np.sqrt(x*x + y*y)
        theta = np.arctan(r)
        theta2 = theta*theta
        poly = np.ones_like(theta)
        power = theta2.copy()
        for k in coeffs:
            poly += k * power
            power *= theta2
        theta_d = theta * poly
        scale = np.where(r > 1e-12, theta_d / r, 1.0)
        return fx*(x*scale) + cx, fy*(y*scale) + cy
    if model == 7:  # FOV
        fx, fy, cx, cy, omega = p
        r = np.sqrt(x*x + y*y)
        if abs(omega) < 1e-12:
            scale = np.ones_like(r)
        else:
            scale = np.where(
                r > 1e-12,
                np.arctan(2*r*math.tan(omega/2.0)) / (omega*r),
                1.0,
            )
        return fx*(x*scale) + cx, fy*(y*scale) + cy
    raise RuntimeError("Unsupported COLMAP camera model {}".format(camera["model_name"]))


def _parse_ply_header(path):
    path = Path(path)
    lines = []
    with path.open("rb") as f:
        if f.readline().strip() != b"ply":
            raise RuntimeError("Not a PLY file: {}".format(path))
        lines.append("ply")
        fmt = None; elements = {}; current = None; vertex_props = []
        while True:
            raw = f.readline()
            if not raw:
                raise RuntimeError("PLY header missing end_header: {}".format(path))
            text = raw.decode("ascii", errors="strict").rstrip("\r\n")
            lines.append(text)
            parts = text.split()
            if parts[:1] == ["format"]:
                fmt = parts[1]
            elif parts[:1] == ["element"] and len(parts) >= 3:
                current = parts[1]; elements[current] = int(parts[2])
            elif parts[:1] == ["property"] and current == "vertex":
                if len(parts) >= 2 and parts[1] == "list":
                    raise RuntimeError("List properties in PLY vertex elements are unsupported")
                if len(parts) != 3 or parts[1] not in _PLY_DTYPES:
                    raise RuntimeError("Unsupported PLY vertex property: {}".format(text))
                vertex_props.append((parts[2], parts[1]))
            if text == "end_header":
                offset = f.tell(); break
    if fmt not in ("binary_little_endian", "ascii"):
        raise RuntimeError("Unsupported PLY format for cleanup: {}".format(fmt))
    if "vertex" not in elements or not vertex_props:
        raise RuntimeError("PLY has no vertex element: {}".format(path))
    for required in ("x", "y", "z"):
        if required not in {name for name, _ in vertex_props}:
            raise RuntimeError("Gaussian PLY missing '{}' property".format(required))
    return {
        "format": fmt, "elements": elements, "vertex_props": vertex_props,
        "header_lines": lines, "data_offset": offset,
    }


def read_ply_element_counts(path):
    return dict(_parse_ply_header(path)["elements"])


def read_ply_vertex_count(path):
    return int(read_ply_element_counts(path).get("vertex", 0))


def _binary_vertex_dtype(props):
    return np.dtype([(name, np.dtype(code)) for name, typ in props for code in [_PLY_DTYPES[typ]]], align=False)


def _load_positions(path, meta):
    count = meta["elements"]["vertex"]
    if meta["format"] == "binary_little_endian":
        dtype = _binary_vertex_dtype(meta["vertex_props"])
        records = np.memmap(path, mode="r", dtype=dtype, offset=meta["data_offset"], shape=(count,))
        positions = np.column_stack((records["x"], records["y"], records["z"])).astype(np.float64, copy=False)
        return positions, records, dtype
    names = [name for name, _ in meta["vertex_props"]]
    xi, yi, zi = names.index("x"), names.index("y"), names.index("z")
    positions = np.empty((count, 3), dtype=np.float64); rows = []
    with Path(path).open("rb") as f:
        f.seek(meta["data_offset"])
        for idx in range(count):
            line = f.readline().decode("ascii")
            rows.append(line)
            parts = line.split()
            positions[idx] = (float(parts[xi]), float(parts[yi]), float(parts[zi]))
    return positions, rows, None


def _write_filtered_ply(source, target, meta, records, keep):
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    count = int(np.count_nonzero(keep))
    lines = []
    replaced = False
    for line in meta["header_lines"]:
        if line.startswith("element vertex "):
            lines.append("element vertex {}".format(count)); replaced = True
        else:
            lines.append(line)
    if not replaced:
        raise RuntimeError("PLY header has no vertex element")
    header = ("\n".join(lines) + "\n").encode("ascii")
    with target.open("wb") as out:
        out.write(header)
        if meta["format"] == "binary_little_endian":
            indices = np.flatnonzero(keep)
            chunk = 100_000
            for start in range(0, len(indices), chunk):
                out.write(np.asarray(records[indices[start:start+chunk]]).tobytes(order="C"))
        else:
            for flag, line in zip(keep.tolist(), records):
                if flag: out.write(line.encode("ascii"))


def cleanup_splat(
    raw_ply,
    output_ply,
    sparse_model,
    masks_dir,
    report_path,
    foreground_ratio=0.70,
    min_views=3,
    min_kept_splats=100,
):
    foreground_ratio = float(foreground_ratio); min_views = int(min_views)
    if not (0.0 < foreground_ratio <= 1.0):
        raise ValueError("foreground_ratio must be in (0, 1]")
    if min_views <= 0:
        raise ValueError("min_views must be > 0")

    raw_ply = Path(raw_ply); output_ply = Path(output_ply); sparse_model = Path(sparse_model); masks_dir = Path(masks_dir)
    if not raw_ply.exists(): raise FileNotFoundError("Raw Splat PLY not found: {}".format(raw_ply))
    for name in ("cameras.bin", "images.bin"):
        if not (sparse_model / name).exists(): raise FileNotFoundError("Splat cleanup missing {}".format(sparse_model / name))

    meta = _parse_ply_header(raw_ply)
    # Gaussian Splat PLYs are vertex-only. Reject other non-empty elements rather than corrupting them.
    extra = {k: v for k, v in meta["elements"].items() if k != "vertex" and v}
    if extra:
        raise RuntimeError("Splat cleanup expects vertex-only Gaussian PLY; found {}".format(extra))
    positions, records, _ = _load_positions(raw_ply, meta)
    n = len(positions)
    cameras = read_cameras_binary(sparse_model / "cameras.bin")
    images = read_images_binary(sparse_model / "images.bin")
    valid_votes = np.zeros(n, dtype=np.uint16)
    fg_votes = np.zeros(n, dtype=np.uint16)
    missing_masks = []
    used_images = 0

    for image_id in sorted(images):
        image = images[image_id]; camera = cameras.get(image["camera_id"])
        if camera is None: continue
        mask_path = masks_dir / (image["name"] + ".png")
        if not mask_path.exists():
            missing_masks.append(image["name"]); continue
        mw, mh, channels, pixels = read_png_u8(mask_path)
        mask_arr = np.frombuffer(pixels, dtype=np.uint8).reshape(mh, mw, channels)[:, :, 0]
        R = _qvec_to_rotmat(image["qvec"]); t = np.asarray(image["tvec"], dtype=np.float64)
        cam = positions @ R.T + t
        z = cam[:, 2]
        front = z > 1e-8
        if not np.any(front): continue
        x = np.zeros(n, dtype=np.float64); y = np.zeros(n, dtype=np.float64)
        x[front] = cam[front, 0] / z[front]; y[front] = cam[front, 1] / z[front]
        u, v = _distort(camera, x, y)
        if camera["width"] and camera["height"] and (camera["width"] != mw or camera["height"] != mh):
            u = u * (mw / float(camera["width"])); v = v * (mh / float(camera["height"]))
        ui = np.rint(u).astype(np.int64); vi = np.rint(v).astype(np.int64)
        valid = front & (ui >= 0) & (vi >= 0) & (ui < mw) & (vi < mh)
        idx = np.flatnonzero(valid)
        if idx.size:
            valid_votes[idx] += 1
            foreground = mask_arr[vi[idx], ui[idx]] >= 128
            if np.any(foreground): fg_votes[idx[foreground]] += 1
        used_images += 1

    ratios = np.divide(fg_votes, valid_votes, out=np.zeros(n, dtype=np.float64), where=valid_votes > 0)
    keep = (valid_votes >= min_views) & (ratios >= foreground_ratio)
    clean_count = int(np.count_nonzero(keep))
    effective_min = min(int(min_kept_splats), n) if n else 0
    if clean_count < effective_min:
        raise RuntimeError(
            "Splat cleanup kept only {} / {} splats (< {}). Check SAM2 masks or relax "
            "--cleanup-ratio / --cleanup-min-views.".format(clean_count, n, effective_min)
        )
    _write_filtered_ply(raw_ply, output_ply, meta, records, keep)

    report = {
        "raw_ply": str(raw_ply), "output_ply": str(output_ply),
        "raw_splats": int(n), "clean_splats": clean_count,
        "removed_splats": int(n - clean_count),
        "removal_ratio": ((n - clean_count) / n) if n else 0.0,
        "keep_ratio": (clean_count / n) if n else 0.0,
        "foreground_ratio_threshold": foreground_ratio,
        "min_views": min_views,
        "registered_images": len(images), "valid_camera_count": used_images,
        "missing_mask_images": sorted(set(missing_masks)),
        "mean_valid_views": float(valid_votes.mean()) if n else 0.0,
        "mean_foreground_support": float(ratios[valid_votes > 0].mean()) if np.any(valid_votes > 0) else 0.0,
    }
    report_path = Path(report_path); report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
