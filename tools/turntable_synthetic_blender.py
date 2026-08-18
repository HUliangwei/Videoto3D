"""Render known-ground-truth Turntable data in Blender.

Example:
blender --background --python tools/turntable_synthetic_blender.py -- \
  --model path/to/model.glb \
  --output workspace/research/turntable/synthetic/chair_nonuniform_280 \
  --profile nonuniform_280 --frames 60
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def _parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--profile", choices=("uniform_360", "nonuniform_360", "nonuniform_280"), default="nonuniform_280")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--focal-mm", type=float, default=50.0)
    p.add_argument("--distance-scale", type=float, default=3.2)
    return p.parse_args(argv)

def _blender_args():
    return [] if "--" not in sys.argv else sys.argv[sys.argv.index("--") + 1:]

def _look_at(obj, target):
    from mathutils import Vector
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def _world_bounds(objects):
    from mathutils import Vector
    points = []
    for obj in objects:
        if obj.type == "MESH":
            points.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if not points:
        raise RuntimeError("Imported model contains no mesh geometry.")
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    center = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))
    radius = max(math.sqrt(sum((p[i] - center[i]) ** 2 for i in range(3))) for p in points)
    return center, max(radius, 1e-6)

def _save_alpha_mask(frame_path, output_path):
    """Create a binary PNG mask from the alpha channel of a saved RGBA render."""
    import bpy

    frame_path = Path(frame_path).resolve()
    output_path = Path(output_path).resolve()

    if not frame_path.exists():
        raise FileNotFoundError(
            "Rendered frame not found: {}".format(frame_path)
        )

    source = bpy.data.images.load(
        str(frame_path),
        check_existing=False,
    )

    try:
        width = int(source.size[0])
        height = int(source.size[1])

        if width <= 0 or height <= 0:
            raise RuntimeError(
                "Loaded render has invalid size: {}x{} ({})".format(
                    width,
                    height,
                    frame_path,
                )
            )

        pixels = list(source.pixels)
        expected = width * height * 4

        if len(pixels) != expected:
            raise RuntimeError(
                "Loaded render pixel count mismatch: "
                "got {}, expected {}".format(
                    len(pixels),
                    expected,
                )
            )

        mask = bpy.data.images.new(
            name="Videoto3D_Turntable_Mask",
            width=width,
            height=height,
            alpha=True,
            float_buffer=False,
        )

        try:
            rgba = [0.0] * expected

            for index in range(width * height):
                alpha = pixels[index * 4 + 3]
                value = 1.0 if alpha > 0.5 else 0.0

                base = index * 4
                rgba[base] = value
                rgba[base + 1] = value
                rgba[base + 2] = value
                rgba[base + 3] = 1.0

            mask.pixels = rgba
            mask.filepath_raw = str(output_path)
            mask.file_format = "PNG"
            mask.save()

        finally:
            bpy.data.images.remove(mask)

    finally:
        bpy.data.images.remove(source)

def main(argv=None):
    import bpy
    from mathutils import Vector

    repo = _repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from pipeline.workflows.turntable.benchmark.profiles import generate_profile

    args = _parse_args(_blender_args() if argv is None else argv)
    model_path = Path(args.model).resolve()
    output = Path(args.output).resolve()
    frames_dir, masks_dir = output / "frames", output / "masks"
    frames_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if model_path.suffix.lower() not in {".glb", ".gltf"}:
        raise ValueError("R0.1 renderer accepts GLB/GLTF.")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model_path))
    imported = list(bpy.context.scene.objects)
    center, radius = _world_bounds(imported)

    pivot = bpy.data.objects.new("TurntablePivot", None)
    pivot.location = center
    bpy.context.scene.collection.objects.link(pivot)
    for obj in imported:
        if obj.parent is None:
            world = obj.matrix_world.copy()
            obj.parent = pivot
            obj.matrix_world = world

    scene = bpy.context.scene
    # Blender render-engine identifiers changed across releases.
    # Prefer the current Eevee identifier, then fall back to older Eevee
    # naming and finally Cycles.
    selected_engine = None
    for engine_name in (
        "BLENDER_EEVEE",
        "BLENDER_EEVEE_NEXT",
        "CYCLES",
    ):
        try:
            scene.render.engine = engine_name
            selected_engine = engine_name
            break
        except TypeError:
            continue

    if selected_engine is None:
        raise RuntimeError(
            "No supported Blender render engine is available."
        )

    print("Videoto3D render engine:", selected_engine)
    scene.render.resolution_x = int(args.width)
    scene.render.resolution_y = int(args.height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True

    cam_data = bpy.data.cameras.new("TurntableCamera")
    cam_data.lens = float(args.focal_mm)
    camera = bpy.data.objects.new("TurntableCamera", cam_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    distance = float(args.distance_scale) * radius
    camera.location = Vector((center[0], center[1] - distance, center[2] + 0.2 * radius))
    _look_at(camera, center)

    for name, energy, loc in (
        ("Key", 900.0, (center[0] + 1.5 * radius, center[1] - 1.5 * radius, center[2] + 2.0 * radius)),
        ("Fill", 350.0, (center[0] - 2.0 * radius, center[1] - 0.5 * radius, center[2] + 0.7 * radius)),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.size = max(radius * 2.0, 0.1)
        light = bpy.data.objects.new(name, data)
        light.location = Vector(loc)
        scene.collection.objects.link(light)
        _look_at(light, center)

    profile = generate_profile(args.profile, args.frames)
    records = []
    for index, angle_deg in enumerate(profile.angles_deg):
        pivot.rotation_euler = (0.0, 0.0, math.radians(float(angle_deg)))
        name = f"frame_{index:04d}.png"
        scene.render.filepath = str(frames_dir / name)
        bpy.ops.render.render(write_still=True)
        _save_alpha_mask(frames_dir / name, masks_dir / name)
        records.append({
            "index": index,
            "frame": f"frames/{name}",
            "mask": f"masks/{name}",
            "angle_deg": float(angle_deg),
            "angle_rad": math.radians(float(angle_deg)),
        })

    camera_matrix = [[float(camera.matrix_world[r][c]) for c in range(4)] for r in range(4)]
    gt = {
        "schema_version": 1,
        "kind": "videoto3d_turntable_synthetic",
        "profile": profile.as_dict(),
        "source_model": str(model_path),
        "rotation_axis_world": [0.0, 0.0, 1.0],
        "rotation_center_world": [float(v) for v in center],
        "camera": {
            "fixed": True,
            "matrix_world": camera_matrix,
            "focal_mm": float(cam_data.lens),
            "sensor_width_mm": float(cam_data.sensor_width),
            "resolution": [int(args.width), int(args.height)],
        },
        "frames": records,
    }
    (output / "ground_truth.json").write_text(json.dumps(gt, indent=2), encoding="utf-8")
    print("Videoto3D Turntable synthetic benchmark ready:", output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
