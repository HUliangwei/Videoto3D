"""Read-only discovery and preview helpers for Videoto3D pipeline artifacts.

This module deliberately lives in ``gui.control`` because it understands the
Videoto3D run layout. The reusable ``gui.viewer`` only receives generic asset
URLs/types and remains unaware of Runs, COLMAP, OpenMVS, Brush, or workspaces.
"""

import json
import re
import struct
from pathlib import Path

from pipeline.colmap_object import read_points3d_binary


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
_FILE_KEYS = {
    "dense", "raw-mesh", "refined-mesh", "glb", "raw-splat", "clean-splat",
}
_SEQUENCE_KEYS = {"frames", "masks", "textures"}
_COLMAP_KEYS = {"sparse", "object-sparse", "camera-trajectory"}


def _validate_run_id(run_id):
    value = str(run_id or "")
    if not _RUN_ID_RE.fullmatch(value):
        raise ValueError("Invalid run id: {!r}".format(value))
    return value


def _run_root(project_root, run_id):
    return Path(project_root) / "workspace" / "runs" / _validate_run_id(run_id)


def _manifest(run_root):
    path = Path(run_root) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Run manifest not found: {}".format(path))
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError("Invalid run manifest: {}".format(path))
    return value


def _inside_run(run_root, path):
    root = Path(run_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("Artifact path escapes run root: {}".format(path))
    return candidate


def _manifest_path(run_root, value, fallback):
    if isinstance(value, str) and value.strip():
        try:
            candidate = _inside_run(run_root, value)
            if candidate.exists():
                return candidate
        except ValueError:
            pass
    return _inside_run(run_root, fallback)


def _stage_status(manifest, branch, stage):
    if branch == "shared":
        entry = manifest.get("shared", {}).get(stage, {})
    else:
        entry = manifest.get("routes", {}).get(branch, {}).get(stage, {})
    return str(entry.get("status", "pending")) if isinstance(entry, dict) else "pending"


def _file_state(path, stage_status):
    path = Path(path)
    if path.is_file() and path.stat().st_size > 0:
        return "ready"
    return "missing" if stage_status == "ready" else "pending"


def _sequence_state(count, expected, stage_status):
    count = int(count)
    expected = int(expected)
    if count > 0 and (expected <= 0 or count >= expected) and stage_status == "ready":
        return "ready"
    if count > 0:
        return "partial"
    return "missing" if stage_status == "ready" else "pending"


def _format_size(size_bytes):
    size = float(size_bytes or 0)
    units = ("B", "KiB", "MiB", "GiB")
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return "{:.0f} {}".format(size, unit) if unit == "B" else "{:.2f} {}".format(size, unit)
        size /= 1024.0
    return "{} B".format(int(size_bytes or 0))


def read_ply_counts(path):
    """Return PLY vertex/face counts by reading only the header."""
    vertices = 0
    faces = 0
    with Path(path).open("rb") as handle:
        total = 0
        for _ in range(4096):
            raw = handle.readline()
            if not raw:
                break
            total += len(raw)
            if total > 1024 * 1024:
                raise RuntimeError("PLY header exceeds 1 MiB: {}".format(path))
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("element vertex "):
                vertices = int(line.rsplit(" ", 1)[-1])
            elif line.startswith("element face "):
                faces = int(line.rsplit(" ", 1)[-1])
            elif line == "end_header":
                return {"vertices": vertices, "faces": faces}
    raise RuntimeError("PLY end_header not found: {}".format(path))


def _colmap_count(model_dir):
    path = Path(model_dir) / "points3D.bin"
    if not path.is_file() or path.stat().st_size < 8:
        return 0
    with path.open("rb") as handle:
        raw = handle.read(8)
    return int(struct.unpack("<Q", raw)[0])



def _quaternion_to_rotation(qw, qx, qy, qz):
    return (
        (1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qw * qz), 2.0 * (qx * qz + qw * qy)),
        (2.0 * (qx * qy + qw * qz), 1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qw * qx)),
        (2.0 * (qx * qz - qw * qy), 2.0 * (qy * qz + qw * qx), 1.0 - 2.0 * (qx * qx + qy * qy)),
    )


def read_colmap_camera_centers(model_dir):
    """Read registered COLMAP images.bin and return world-space camera centers.

    COLMAP stores world-to-camera pose x_c = R x_w + t, so the camera center
    in world coordinates is C = -R^T t.
    """
    path = Path(model_dir) / "images.bin"
    if not path.is_file():
        raise FileNotFoundError("COLMAP images.bin not found: {}".format(path))
    result = []
    fixed = struct.Struct("<i7di")
    with path.open("rb") as handle:
        raw = handle.read(8)
        if len(raw) != 8:
            raise RuntimeError("Invalid COLMAP images.bin header: {}".format(path))
        count = struct.unpack("<Q", raw)[0]
        for _ in range(count):
            data = handle.read(fixed.size)
            if len(data) != fixed.size:
                raise RuntimeError("Truncated COLMAP images.bin: {}".format(path))
            image_id, qw, qx, qy, qz, tx, ty, tz, camera_id = fixed.unpack(data)
            name_bytes = bytearray()
            while True:
                byte = handle.read(1)
                if not byte:
                    raise RuntimeError("Truncated COLMAP image name: {}".format(path))
                if byte == b"\x00":
                    break
                name_bytes.extend(byte)
            point_count_raw = handle.read(8)
            if len(point_count_raw) != 8:
                raise RuntimeError("Truncated COLMAP points2D count: {}".format(path))
            point_count = struct.unpack("<Q", point_count_raw)[0]
            handle.seek(int(point_count) * 24, 1)
            rotation = _quaternion_to_rotation(qw, qx, qy, qz)
            tvec = (tx, ty, tz)
            center = tuple(
                -sum(rotation[row][column] * tvec[row] for row in range(3))
                for column in range(3)
            )
            result.append({
                "image_id": int(image_id),
                "camera_id": int(camera_id),
                "name": name_bytes.decode("utf-8", errors="replace"),
                "center": center,
            })
    return result


def colmap_camera_centers_as_ply(model_dir):
    centers = read_colmap_camera_centers(model_dir)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment Videoto3D COLMAP camera centers\n"
        "element vertex {}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).format(len(centers)).encode("ascii")
    vertex = struct.Struct("<fffBBB")
    body = bytearray(vertex.size * len(centers))
    offset = 0
    for item in centers:
        x, y, z = item["center"]
        vertex.pack_into(body, offset, float(x), float(y), float(z), 240, 164, 108)
        offset += vertex.size
    return header + bytes(body)


def colmap_model_as_ply(model_dir):
    """Convert COLMAP points3D.bin to a compact browser-readable RGB PLY."""
    model_dir = Path(model_dir)
    points_path = model_dir / "points3D.bin"
    if not points_path.is_file():
        raise FileNotFoundError("COLMAP points3D.bin not found: {}".format(points_path))
    points = read_points3d_binary(points_path)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment Videoto3D browser preview\n"
        "element vertex {}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).format(len(points)).encode("ascii")
    vertex = struct.Struct("<fffBBB")
    body = bytearray(vertex.size * len(points))
    offset = 0
    for point_id in sorted(points):
        point = points[point_id]
        xyz = point["xyz"]
        rgb = point["rgb"]
        vertex.pack_into(
            body,
            offset,
            float(xyz[0]), float(xyz[1]), float(xyz[2]),
            int(rgb[0]), int(rgb[1]), int(rgb[2]),
        )
        offset += vertex.size
    return header + bytes(body)


def _texture_files(openmvs_dir):
    openmvs_dir = Path(openmvs_dir)
    if not openmvs_dir.exists():
        return []
    preferred = [
        p for p in openmvs_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES and "map_kd" in p.name.lower()
    ]
    if preferred:
        return sorted(preferred)
    # Fallback for OpenMVS builds that use a different atlas filename.
    return sorted(
        p for p in openmvs_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )


def _sequence_files(run_root, key):
    run_root = Path(run_root)
    if key == "frames":
        return sorted((run_root / "frames").glob("frame_*.jpg"))
    if key == "masks":
        return sorted((run_root / "masks").glob("frame_*.jpg.png"))
    if key == "textures":
        return _texture_files(run_root / "mesh" / "openmvs")
    raise ValueError("Unknown sequence artifact: {}".format(key))


def _artifact_paths(run_root, manifest, run_id):
    run_root = Path(run_root)
    openmvs = run_root / "mesh" / "openmvs"
    mesh = manifest.get("routes", {}).get("mesh", {})
    splat = manifest.get("routes", {}).get("splat", {})
    training = splat.get("training", {}) if isinstance(splat.get("training", {}), dict) else {}
    glb = mesh.get("glb", {}) if isinstance(mesh.get("glb", {}), dict) else {}
    final_splat = splat.get("ply", {}) if isinstance(splat.get("ply", {}), dict) else {}
    return {
        "sparse": run_root / "colmap" / "sparse" / "0",
        "camera-trajectory": run_root / "colmap" / "sparse" / "0",
        "dense": openmvs / "scene_dense.ply",
        "raw-mesh": openmvs / "scene_mesh.ply",
        "refined-mesh": openmvs / "scene_refined.ply",
        "glb": _manifest_path(run_root, glb.get("path"), "output/{}.glb".format(run_id)),
        "object-sparse": run_root / "splat" / "dataset" / "sparse" / "0",
        "raw-splat": _manifest_path(run_root, training.get("raw_path"), "splat/raw/{}_raw.ply".format(run_id)),
        "clean-splat": _manifest_path(run_root, final_splat.get("path"), "output/{}_splat.ply".format(run_id)),
    }


def _file_metrics(path, ply=False):
    path = Path(path)
    if not path.is_file():
        return {}
    metrics = {"size": _format_size(path.stat().st_size), "size_bytes": path.stat().st_size}
    if ply:
        try:
            metrics.update(read_ply_counts(path))
        except (OSError, RuntimeError, ValueError):
            pass
    return metrics


def _item(key, label, stage, state, kind, description, metrics=None, **extra):
    item = {
        "key": key,
        "label": label,
        "stage": stage,
        "state": state,
        "kind": kind,
        "description": description,
        "metrics": metrics or {},
    }
    item.update(extra)
    return item


def build_artifact_catalog(project_root, run_id):
    run_id = _validate_run_id(run_id)
    run_root = _run_root(project_root, run_id)
    manifest = _manifest(run_root)
    paths = _artifact_paths(run_root, manifest, run_id)

    frames = _sequence_files(run_root, "frames")
    masks = _sequence_files(run_root, "masks")
    textures = _sequence_files(run_root, "textures")

    shared = [
        _item(
            "frames", "Frames", "Shared · Extract",
            _sequence_state(len(frames), len(frames), _stage_status(manifest, "shared", "extract")),
            "image-sequence",
            "FFmpeg 从输入视频抽取的多视角 RGB 图像；后续 SfM、Mask 与两条 Route 都建立在这些视角上。",
            {"count": len(frames)}, count=len(frames),
            frame_base_url="/api/runs/{}/artifacts/frames".format(run_id),
        ),
        _item(
            "masks", "SAM2 Masks", "Shared · Mask",
            _sequence_state(len(masks), len(frames), _stage_status(manifest, "shared", "mask")),
            "mask-sequence",
            "SAM2 对目标主体的逐帧二值分割。Overlay 用于检查跟踪是否漏掉主体或吃进背景。",
            {"masks": len(masks), "frames": len(frames)}, count=min(len(frames), len(masks)),
            frame_base_url="/api/runs/{}/artifacts/frames".format(run_id),
            mask_base_url="/api/runs/{}/artifacts/masks".format(run_id),
        ),
        _item(
            "sparse", "COLMAP Sparse", "Shared · Sparse",
            "ready" if (paths["sparse"] / "points3D.bin").is_file() else (
                "missing" if _stage_status(manifest, "shared", "sparse") == "ready" else "pending"
            ),
            "pointcloud",
            "Structure-from-Motion 恢复的稀疏 3D 特征点；它证明相机位姿和多视角几何已经被建立。",
            {"points": _colmap_count(paths["sparse"])},
            asset_url="/api/runs/{}/artifacts/file/sparse".format(run_id),
        ),
    ]

    shared.append(
        _item(
            "camera-trajectory", "Camera Trajectory", "Shared · Sparse",
            "ready" if (paths["camera-trajectory"] / "images.bin").is_file() else (
                "missing" if _stage_status(manifest, "shared", "sparse") == "ready" else "pending"
            ),
            "pointcloud",
            "COLMAP registered camera centers. Orbit mode reflects physical camera motion; Turntable mode shows the equivalent virtual camera motion recovered from rigid-object features.",
            {"cameras": len(read_colmap_camera_centers(paths["camera-trajectory"])) if (paths["camera-trajectory"] / "images.bin").is_file() else 0},
            asset_url="/api/runs/{}/artifacts/file/camera-trajectory".format(run_id),
        )
    )

    mesh = [
        _item(
            "dense", "Dense Cloud", "Mesh · Dense",
            _file_state(paths["dense"], _stage_status(manifest, "mesh", "dense")),
            "pointcloud",
            "OpenMVS Multi-View Stereo 将稀疏特征扩展成高密度表面点云。",
            _file_metrics(paths["dense"], ply=True),
            asset_url="/api/runs/{}/artifacts/file/dense".format(run_id),
        ),
        _item(
            "raw-mesh", "Raw Mesh", "Mesh · Reconstruct",
            _file_state(paths["raw-mesh"], _stage_status(manifest, "mesh", "reconstruct")),
            "mesh-ply",
            "由 Dense Cloud 重建出的第一版三角网格，尚未经过多视角表面优化。",
            _file_metrics(paths["raw-mesh"], ply=True),
            asset_url="/api/runs/{}/artifacts/file/raw-mesh".format(run_id),
        ),
        _item(
            "refined-mesh", "Refined Mesh", "Mesh · Refine",
            _file_state(paths["refined-mesh"], _stage_status(manifest, "mesh", "refine")),
            "mesh-ply",
            "OpenMVS 再利用多视角图像优化后的网格；适合与 Raw Mesh 对比几何变化。",
            _file_metrics(paths["refined-mesh"], ply=True),
            asset_url="/api/runs/{}/artifacts/file/refined-mesh".format(run_id),
        ),
        _item(
            "textures", "Texture Atlas", "Mesh · Texture",
            _sequence_state(len(textures), len(textures), _stage_status(manifest, "mesh", "texture")),
            "image-sequence",
            "TextureMesh 将多张照片投影并打包成纹理图集，随后由 OBJ/GLB 的 UV 坐标采样。",
            {"count": len(textures)}, count=len(textures),
            image_base_url="/api/runs/{}/artifacts/textures".format(run_id),
        ),
        _item(
            "glb", "Final GLB", "Mesh · GLB",
            _file_state(paths["glb"], _stage_status(manifest, "mesh", "glb")),
            "glb",
            "可直接部署到浏览器/个人网站的最终传统 3D 资产：Mesh + Material + Texture。",
            _file_metrics(paths["glb"]),
            asset_url="/api/runs/{}/artifacts/file/glb".format(run_id),
        ),
    ]

    splat = [
        _item(
            "object-sparse", "Object Sparse", "Splat · Object Init",
            "ready" if (paths["object-sparse"] / "points3D.bin").is_file() else (
                "missing" if _stage_status(manifest, "splat", "training") == "ready" else "pending"
            ),
            "pointcloud",
            "把 Shared COLMAP points3D 投影回 SAM2 Mask 后筛出的目标点，用作 Brush 的主体优先初始化。",
            {"points": _colmap_count(paths["object-sparse"])},
            asset_url="/api/runs/{}/artifacts/file/object-sparse".format(run_id),
        ),
        _item(
            "raw-splat", "Raw Splat", "Splat · Brush",
            _file_state(paths["raw-splat"], _stage_status(manifest, "splat", "training")),
            "splat",
            "Brush 训练结束时的原始 Gaussian 集合；保留它用于观察训练产生的背景/halo。",
            _file_metrics(paths["raw-splat"], ply=True),
            asset_url="/api/runs/{}/artifacts/file/raw-splat".format(run_id),
        ),
        _item(
            "clean-splat", "Clean Splat", "Splat · Cleanup",
            _file_state(paths["clean-splat"], _stage_status(manifest, "splat", "ply")),
            "splat",
            "将最终 Gaussian 再投影到多视角 SAM2 Mask 做投票，删除不属于目标的 Gaussian。",
            _file_metrics(paths["clean-splat"], ply=True),
            asset_url="/api/runs/{}/artifacts/file/clean-splat".format(run_id),
        ),
    ]

    return {
        "run_id": run_id,
        "groups": [
            {"key": "shared", "label": "Shared", "artifacts": shared},
            {"key": "mesh", "label": "Mesh Route", "artifacts": mesh},
            {"key": "splat", "label": "Splat Route", "artifacts": splat},
        ],
    }


def resolve_sequence_item(project_root, run_id, key, index):
    if key not in _SEQUENCE_KEYS:
        raise ValueError("Unknown sequence artifact: {}".format(key))
    run_root = _run_root(project_root, run_id)
    files = _sequence_files(run_root, key)
    index = int(index)
    if index < 0 or index >= len(files):
        raise IndexError("{} index out of range: {}".format(key, index))
    return files[index]


def resolve_artifact_file(project_root, run_id, key):
    if key not in _FILE_KEYS:
        raise ValueError("Unknown file artifact: {}".format(key))
    run_root = _run_root(project_root, run_id)
    manifest = _manifest(run_root)
    path = _artifact_paths(run_root, manifest, _validate_run_id(run_id))[key]
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError("Artifact not found: {}".format(key))
    return path


def resolve_colmap_model(project_root, run_id, key):
    if key not in _COLMAP_KEYS:
        raise ValueError("Unknown COLMAP artifact: {}".format(key))
    run_root = _run_root(project_root, run_id)
    manifest = _manifest(run_root)
    model = _artifact_paths(run_root, manifest, _validate_run_id(run_id))[key]
    if not (model / "points3D.bin").is_file():
        raise FileNotFoundError("COLMAP artifact not found: {}".format(key))
    return model
