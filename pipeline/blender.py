import subprocess
from pathlib import Path

from pipeline.processes import launch_detached


def build_blender_glb_command(
    blender_path,
    script_path,
    input_obj,
    output_glb,
):
    return [
        str(Path(blender_path)),
        "--background",
        "--factory-startup",
        "--python",
        str(Path(script_path)),
        "--",
        "--input",
        str(Path(input_obj)),
        "--output",
        str(Path(output_glb)),
    ]


def export_obj_to_glb(
    blender_path,
    script_path,
    input_obj,
    output_glb,
    working_dir,
    log_path,
):
    blender_path = Path(blender_path)
    script_path = Path(script_path)
    input_obj = Path(input_obj)
    output_glb = Path(output_glb)
    working_dir = Path(working_dir)
    log_path = Path(log_path)

    if not blender_path.exists():
        raise FileNotFoundError(
            "Blender not found: {}".format(blender_path)
        )

    if not script_path.exists():
        raise FileNotFoundError(
            "Blender export script not found: {}".format(script_path)
        )

    if not input_obj.exists():
        raise FileNotFoundError(
            "OpenMVS OBJ not found: {}".format(input_obj)
        )

    working_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_glb.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_glb.exists():
        output_glb.unlink()

    command = build_blender_glb_command(
        blender_path=blender_path,
        script_path=script_path,
        input_obj=input_obj,
        output_glb=output_glb,
    )

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log:
        result = subprocess.run(
            command,
            cwd=str(working_dir),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        raise RuntimeError(
            "Blender GLB export failed with exit code {}. "
            "See {}".format(
                result.returncode,
                log_path,
            )
        )

    if not output_glb.exists():
        raise RuntimeError(
            "Blender exited successfully but GLB was not created: {}. "
            "See {}".format(
                output_glb,
                log_path,
            )
        )

    if output_glb.stat().st_size == 0:
        raise RuntimeError(
            "Blender created an empty GLB: {}".format(output_glb)
        )

    return {
        "input_obj": str(input_obj),
        "output_glb": str(output_glb),
        "size_bytes": output_glb.stat().st_size,
        "log": str(log_path),
    }


def build_blender_view_command(
    blender_path,
    script_path,
    input_asset,
):
    return [
        str(Path(blender_path)),
        "--factory-startup",
        "--python",
        str(Path(script_path)),
        "--",
        "--input",
        str(Path(input_asset)),
    ]


def launch_asset_viewer(
    blender_path,
    script_path,
    input_asset,
    working_dir,
):
    blender_path = Path(blender_path)
    script_path = Path(script_path)
    input_asset = Path(input_asset)
    working_dir = Path(working_dir)

    if not blender_path.exists():
        raise FileNotFoundError(
            "Blender not found: {}".format(blender_path)
        )

    if not script_path.exists():
        raise FileNotFoundError(
            "Blender viewer script not found: {}".format(script_path)
        )

    if not input_asset.exists():
        raise FileNotFoundError(
            "Asset not found: {}".format(input_asset)
        )

    working_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = build_blender_view_command(
        blender_path=blender_path,
        script_path=script_path,
        input_asset=input_asset,
    )

    process = launch_detached(
        command,
        cwd=working_dir,
    )

    return process.pid
