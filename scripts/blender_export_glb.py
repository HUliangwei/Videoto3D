import argparse
import sys
from pathlib import Path

import bpy


def parse_args():
    if "--" not in sys.argv:
        raise RuntimeError(
            "Expected Blender script arguments after '--'."
        )

    argv = sys.argv[
        sys.argv.index("--") + 1:
    ]

    parser = argparse.ArgumentParser(
        description="Videoto3D Blender OBJ to GLB exporter"
    )

    parser.add_argument(
        "--input",
        required=True,
    )
    parser.add_argument(
        "--output",
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


def import_obj(input_path):
    result = bpy.ops.wm.obj_import(
        filepath=str(input_path),
    )

    if "FINISHED" not in result:
        raise RuntimeError(
            "Blender OBJ import did not finish successfully."
        )


def mesh_stats():
    mesh_objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    ]

    if not mesh_objects:
        raise RuntimeError(
            "OBJ import produced no mesh objects."
        )

    vertices = sum(
        len(obj.data.vertices)
        for obj in mesh_objects
    )

    polygons = sum(
        len(obj.data.polygons)
        for obj in mesh_objects
    )

    return (
        len(mesh_objects),
        vertices,
        polygons,
    )


def export_glb(output_path):
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
    )

    if "FINISHED" not in result:
        raise RuntimeError(
            "Blender GLB export did not finish successfully."
        )


def main():
    args = parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            "Input OBJ does not exist: {}".format(input_path)
        )

    print("Videoto3D Blender Export")
    print("Input :", input_path)
    print("Output:", output_path)

    clear_scene()
    import_obj(input_path)

    objects, vertices, polygons = mesh_stats()

    print("Mesh objects:", objects)
    print("Vertices    :", vertices)
    print("Polygons    :", polygons)

    export_glb(output_path)

    if not output_path.exists():
        raise RuntimeError(
            "GLB output was not created."
        )

    print(
        "GLB bytes   :",
        output_path.stat().st_size,
    )
    print("Videoto3D Blender export completed.")


if __name__ == "__main__":
    main()
