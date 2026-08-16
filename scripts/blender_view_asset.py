import argparse
import sys
from pathlib import Path

import bpy


def parse_args():
    if "--" not in sys.argv:
        raise RuntimeError(
            "Expected Videoto3D viewer arguments after '--'."
        )

    argv = sys.argv[
        sys.argv.index("--") + 1:
    ]

    parser = argparse.ArgumentParser(
        description="Videoto3D Blender asset viewer"
    )
    parser.add_argument(
        "--input",
        required=True,
    )

    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(
        action="SELECT"
    )
    bpy.ops.object.delete(
        use_global=False
    )


def import_asset(path):
    suffix = path.suffix.lower()

    if suffix == ".obj":
        result = bpy.ops.wm.obj_import(
            filepath=str(path),
        )
    elif suffix in (".glb", ".gltf"):
        result = bpy.ops.import_scene.gltf(
            filepath=str(path),
        )
    elif suffix == ".ply":
        result = bpy.ops.wm.ply_import(
            filepath=str(path),
        )
    else:
        raise RuntimeError(
            "Unsupported viewer asset type: {}".format(suffix)
        )

    if "FINISHED" not in result:
        raise RuntimeError(
            "Blender could not import {}".format(path)
        )


def select_meshes():
    bpy.ops.object.select_all(
        action="DESELECT"
    )

    mesh_objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    ]

    if not mesh_objects:
        raise RuntimeError(
            "Imported asset contains no mesh objects."
        )

    for obj in mesh_objects:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = mesh_objects[0]

    return mesh_objects


def asset_material_stats(mesh_objects):
    materials = {
        material.name
        for obj in mesh_objects
        for material in obj.data.materials
        if material is not None
    }

    images = {
        image.name
        for image in bpy.data.images
        if image.source != "VIEWER"
    }

    return len(materials), len(images)


def apply_view_settings():
    screen = bpy.context.screen

    if screen is None:
        return 0.2

    applied = False

    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue

        space = area.spaces.active
        space.shading.type = "MATERIAL"

        window_region = next(
            (
                region
                for region in area.regions
                if region.type == "WINDOW"
            ),
            None,
        )

        if window_region is not None:
            try:
                with bpy.context.temp_override(
                    area=area,
                    region=window_region,
                    space_data=space,
                ):
                    bpy.ops.view3d.view_selected(
                        use_all_regions=False
                    )
            except Exception as exc:
                print(
                    "Viewer frame warning:",
                    exc,
                )

        applied = True

    if applied:
        print(
            "Viewport    : Material Preview"
        )
        return None

    return 0.2


def main():
    args = parse_args()
    input_path = Path(args.input).resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            "Asset does not exist: {}".format(input_path)
        )

    clear_scene()
    import_asset(input_path)
    mesh_objects = select_meshes()

    vertices = sum(
        len(obj.data.vertices)
        for obj in mesh_objects
    )
    polygons = sum(
        len(obj.data.polygons)
        for obj in mesh_objects
    )

    materials, images = asset_material_stats(
        mesh_objects
    )

    print("Videoto3D Asset Viewer")
    print("Asset       :", input_path)
    print("Mesh objects:", len(mesh_objects))
    print("Vertices    :", vertices)
    print("Polygons    :", polygons)
    print("Materials   :", materials)
    print("Images      :", images)
    print("Viewport    : switching to Material Preview")
    print("")
    print(
        "Viewer tip: if needed, press Home in the 3D Viewport "
        "to frame the whole model."
    )

    bpy.app.timers.register(
        apply_view_settings,
        first_interval=0.2,
    )

    # Keep Blender open. Without --background, control returns to the GUI
    # after this script completes.


if __name__ == "__main__":
    main()
