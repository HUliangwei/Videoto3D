import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BOOTSTRAP_ROOT = Path(__file__).resolve().parent
if __name__ == "__main__" and os.name == "nt":
    from bootstrap import bootstrap_entry
    bootstrap_result = bootstrap_entry(BOOTSTRAP_ROOT, sys.argv[1:])
    if bootstrap_result is not None:
        sys.exit(bootstrap_result)

from pipeline.video import extract_frames
from pipeline.colmap import run_sparse_reconstruction, launch_colmap_gui
from pipeline.openmvs import (
    DEFAULT_MESH_PROFILE,
    mesh_recipe_matches,
    normalize_mesh_profile,
    run_mesh_pipeline,
)
from pipeline.blender import export_obj_to_glb, launch_asset_viewer
from pipeline.brush import (
    DEFAULT_STEPS as BRUSH_DEFAULT_STEPS,
    DEFAULT_MAX_SPLATS as BRUSH_DEFAULT_MAX_SPLATS,
    DEFAULT_MAX_RESOLUTION as BRUSH_DEFAULT_MAX_RESOLUTION,
    run_brush_training,
    launch_brush_viewer,
)
from pipeline.splat_cleanup import cleanup_splat
from pipeline.quality import generate_quality_report
from pipeline.capture_mode import (
    DEFAULT_CAPTURE_MODE, capture_mode_label, normalize_capture_mode, sparse_mask_path,
)
from pipeline.segmentation_runtime import resolve_segmentation_runtime
from pipeline.env_manager import environment_status, repair_environment, environment_python
from pipeline.segmentation import (
    copy_frames_for_masked_run,
    run_segmentation,
    run_mask_qa_viewer,
    validate_masks,
    prepare_openmvs_masks,
)
from pipeline.cli_commands import (
    command_spec,
    parse_cli_args,
    print_cli_help,
    print_command_annotation,
)
from gui.control.server.launcher import run_gui_server
from pipeline.run_workspace import (
    create_or_load_run,
    copy_source_into_run,
    invalidate_route_stages,
    invalidate_shared_stages,
    list_run_summaries,
    load_run_manifest,
    resolve_run_root as resolve_workspace_run_root,
    route_stage_status,
    shared_stage_status,
    update_route_stage,
    update_capture_mode,
    update_run_source,
    update_shared_stage,
    validate_run_id,
)


ROOT = Path(__file__).resolve().parent

CONFIG_DIR = ROOT / "config"
RUNTIME = ROOT / "runtime"
WORKSPACE = ROOT / "workspace"

TOOLS_JSON = CONFIG_DIR / "tools.json"
LEGACY_TOOLS_JSON = CONFIG_DIR / "tool.json"

OPENMVS_REQUIRED_EXECUTABLES = (
    "InterfaceCOLMAP.exe",
    "DensifyPointCloud.exe",
    "ReconstructMesh.exe",
    "RefineMesh.exe",
    "TextureMesh.exe",
)

OPENMVS_HELP_ACCEPTED_EXIT_CODES = (0, 1)


for directory in (
    CONFIG_DIR,
    RUNTIME,
    WORKSPACE,
):
    directory.mkdir(parents=True, exist_ok=True)


def _read_config_file(path):
    path = Path(path)

    if not path.exists():
        return None

    try:
        raw = path.read_text(
            encoding="utf-8-sig"
        ).strip()
    except Exception:
        return None

    if not raw:
        return None

    try:
        value = json.loads(raw)
    except Exception:
        return None

    if not isinstance(value, dict):
        return None

    tools = value.get("tools")

    if not isinstance(tools, dict):
        return None

    return value


def load_config(
    primary_path=TOOLS_JSON,
    legacy_path=LEGACY_TOOLS_JSON,
):
    primary = _read_config_file(
        primary_path
    )

    if primary is not None:
        return primary

    legacy = _read_config_file(
        legacy_path
    )

    if legacy is not None:
        return legacy

    return {"tools": {}}


config = load_config()


def save_tool(name, path, source):
    config.setdefault("tools", {})[name] = {
        "path": str(Path(path).resolve()),
        "source": source,
    }

    payload = json.dumps(
        config,
        indent=2,
        ensure_ascii=False,
    )

    temp_path = TOOLS_JSON.with_suffix(
        ".json.tmp"
    )

    temp_path.write_text(
        payload,
        encoding="utf-8",
    )

    os.replace(
        str(temp_path),
        str(TOOLS_JSON),
    )


def saved_tool(name):
    value = (
        config
        .get("tools", {})
        .get(name, {})
        .get("path")
    )

    if not value:
        return None

    path = Path(value)

    if path.exists():
        return path

    return None


def run_tool(path, *args):
    path = Path(path)

    if path.suffix.lower() in (".bat", ".cmd"):
        command = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(path),
        ] + list(args)

    else:
        command = [
            str(path),
        ] + list(args)

    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=20,
        )

        return (
            result.returncode,
            result.stdout.strip(),
        )

    except Exception as exc:
        return -1, str(exc)


def find_candidates(name):
    candidates = []

    saved = saved_tool(name)

    if saved:
        candidates.append(
            ("saved", saved)
        )

    if name == "blender":
        blender_paths = sorted(
            glob.glob(
                r"C:\Program Files\Blender Foundation"
                r"\Blender *\blender.exe"
            ),
            reverse=True,
        )

        for item in blender_paths:
            candidates.append(
                ("detected", Path(item))
            )

    if name == "ffmpeg":
        for item in RUNTIME.glob(
            "ffmpeg/**/ffmpeg.exe"
        ):
            candidates.append(
                ("runtime", item)
            )

    if name == "openmvs":
        for item in RUNTIME.glob(
            "openmvs/**/InterfaceCOLMAP.exe"
        ):
            candidates.append(
                ("runtime", item.parent)
            )

    path_names = {
        "colmap": [
            "colmap",
            "COLMAP.bat",
        ],
        "brush": [
            "brush",
        ],
        "blender": [
            "blender",
        ],
        "ffmpeg": [
            "ffmpeg",
        ],
        "openmvs": [
            "InterfaceCOLMAP",
        ],
    }

    for executable in path_names[name]:
        found = shutil.which(executable)

        if found:
            found = Path(found)

            if name == "openmvs":
                found = found.parent

            candidates.append(
                ("PATH", found)
            )

    unique = []
    seen = set()

    for source, path in candidates:
        key = str(path).lower()

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            (source, path)
        )

    return unique


def openmvs_help_exit_code_is_valid(returncode):
    return returncode in OPENMVS_HELP_ACCEPTED_EXIT_CODES


def validate_openmvs(path):
    base = (
        path
        if path.is_dir()
        else path.parent
    )

    missing = [
        executable
        for executable in OPENMVS_REQUIRED_EXECUTABLES
        if not (base / executable).exists()
    ]

    if missing:
        return (
            False,
            "Missing: " + ", ".join(missing),
        )

    interface_colmap = base / "InterfaceCOLMAP.exe"

    try:
        result = subprocess.run(
            [
                str(interface_colmap),
                "-h",
            ],
            cwd=str(base),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )

    except subprocess.TimeoutExpired:
        return (
            False,
            "InterfaceCOLMAP launch timed out",
        )

    except OSError as exc:
        return (
            False,
            "InterfaceCOLMAP could not start: {}".format(exc),
        )

    if not openmvs_help_exit_code_is_valid(result.returncode):
        return (
            False,
            "InterfaceCOLMAP abnormal exit code: {}".format(
                result.returncode
            ),
        )

    return (
        True,
        "OpenMVS core tools validated; "
        "InterfaceCOLMAP help exit={}".format(
            result.returncode
        ),
    )


def validate_tool(name, path):
    path = Path(path)

    if name == "colmap":

        code, output = run_tool(
            path,
            "version",
        )

        if code != 0:
            code, output = run_tool(
                path,
                "-h",
            )

        ok = (
            code == 0
            and "COLMAP" in output
        )

        return ok, output

    if name == "brush":

        code, output = run_tool(
            path,
            "--help",
        )

        return (
            code == 0,
            output,
        )

    if name == "blender":

        code, output = run_tool(
            path,
            "--version",
        )

        ok = (
            code == 0
            and "Blender" in output
        )

        return ok, output

    if name == "ffmpeg":

        code, output = run_tool(
            path,
            "-version",
        )

        ok = (
            code == 0
            and
            "ffmpeg version"
            in output.lower()
        )

        return ok, output

    if name == "openmvs":
        return validate_openmvs(path)

    return (
        False,
        "Unknown tool",
    )


def resolve_tool(name):
    for source, path in find_candidates(name):
        ok, output = validate_tool(
            name,
            path,
        )

        if ok:
            save_tool(
                name,
                path,
                source,
            )

            first_line = (
                output.splitlines()[0]
                if output
                else "validated"
            )

            return (
                True,
                path,
                source,
                first_line,
            )

    print(
        "\n{} was not validated automatically."
        .format(name)
    )

    raw = input(
        "Existing path, "
        "or press Enter to leave missing: "
    ).strip().strip('"')

    if raw:
        path = Path(raw)

        if (
            name == "openmvs"
            and path.is_file()
        ):
            path = path.parent

        ok, output = validate_tool(
            name,
            path,
        )

        if ok:
            save_tool(
                name,
                path,
                "user",
            )

            first_line = (
                output.splitlines()[0]
                if output
                else "validated"
            )

            return (
                True,
                path,
                "user",
                first_line,
            )

        print(
            "Validation failed:",
            output.splitlines()[0]
            if output
            else "unknown error",
        )

    return (
        False,
        None,
        None,
        None,
    )


def check_environment():
    print("=" * 68)
    print("Videoto3D Environment Doctor")
    print("Root   :", ROOT)
    print(
        "Python :",
        sys.version.split()[0],
        sys.executable,
    )
    print("=" * 68)

    missing = []
    resolved = {}

    tools = (
        "colmap",
        "brush",
        "blender",
        "ffmpeg",
        "openmvs",
    )

    for name in tools:
        (
            ok,
            path,
            source,
            detail,
        ) = resolve_tool(name)

        if ok:
            resolved[name] = Path(path)

            print(
                "[READY] {:8} {} [{}]"
                .format(
                    name,
                    path,
                    source,
                )
            )

            print(
                "        {}"
                .format(detail)
            )
        else:
            print(
                "[ERROR] {:8} not ready"
                .format(name)
            )
            missing.append(name)

    print("=" * 68)

    if missing:
        print(
            "Environment incomplete:",
            ", ".join(missing),
        )
        print(
            "Run the SAME command "
            "after fixing dependencies:"
        )
        print("python app.py")
        return False, resolved

    print("Environment READY")
    print(
        "Tool paths saved to:",
        TOOLS_JSON,
    )
    return True, resolved


def check_required_tools(tool_names):
    """Validate only the external tools required by one canonical command."""
    print("=" * 68)
    print("Videoto3D Environment Check")
    print("Root   :", ROOT)
    print(
        "Python :",
        sys.version.split()[0],
        sys.executable,
    )
    print(
        "Needed :",
        ", ".join(tool_names),
    )
    print("=" * 68)

    missing = []
    resolved = {}

    for name in tool_names:
        (
            ok,
            path,
            source,
            detail,
        ) = resolve_tool(name)

        if ok:
            resolved[name] = Path(path)
            print(
                "[READY] {:8} {} [{}]".format(
                    name,
                    path,
                    source,
                )
            )
            print("        {}".format(detail))
        else:
            print("[ERROR] {:8} not ready".format(name))
            missing.append(name)

    print("=" * 68)

    if missing:
        print(
            "Required environment incomplete:",
            ", ".join(missing),
        )
        return False, resolved

    print("Required environment READY")
    return True, resolved


def resolve_run_root(run_id):
    return resolve_workspace_run_root(WORKSPACE / "runs", run_id)


def _require_run(run_id):
    run_root = resolve_run_root(run_id)
    if not (run_root / "run.json").exists():
        raise FileNotFoundError(
            "Run {!r} does not exist. Create it with: python app.py run extract --run {} --input <video>"
            .format(run_id, run_id)
        )
    return run_root, load_run_manifest(run_root)


def _rel(run_root, path):
    try:
        return str(Path(path).relative_to(Path(run_root)))
    except ValueError:
        return str(Path(path))


def _reset_dirs(run_root, names):
    run_root = Path(run_root)
    for name in names:
        path = run_root / name
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def invalidate_after_extract(run_root):
    _reset_dirs(run_root, ("masks", "segmentation", "colmap", "mesh", "splat", "output"))
    for group in ("shared", "mesh", "splat"):
        _reset_dirs(run_root / "logs", (group,))
    invalidate_shared_stages(run_root, ("mask", "sparse"))
    invalidate_route_stages(run_root, "mesh")
    invalidate_route_stages(run_root, "splat")

def invalidate_after_mask(run_root):
    manifest = load_run_manifest(run_root)
    capture_mode = normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE))
    reset_names = ["mesh", "splat", "output"]
    if capture_mode == "turntable":
        # Turntable SfM extracts features through the SAM2 masks, therefore a
        # mask change invalidates the Shared COLMAP model as well.
        reset_names.append("colmap")
        for log_path in (run_root / "logs" / "shared").glob("colmap_*.log"):
            log_path.unlink(missing_ok=True)
        invalidate_shared_stages(run_root, ("sparse",))
    _reset_dirs(run_root, tuple(reset_names))
    _reset_dirs(run_root / "logs", ("mesh", "splat"))
    invalidate_route_stages(run_root, "mesh")
    invalidate_route_stages(run_root, "splat")

def invalidate_after_sparse(run_root):
    _reset_dirs(run_root, ("mesh", "splat", "output"))
    _reset_dirs(run_root / "logs", ("mesh", "splat"))
    invalidate_route_stages(run_root, "mesh")
    invalidate_route_stages(run_root, "splat")

def run_extract(resolved, options):
    run_id = validate_run_id(options["run"])
    capture_mode = normalize_capture_mode(options.get("capture_mode", DEFAULT_CAPTURE_MODE))
    run_root, _ = create_or_load_run(WORKSPACE / "runs", run_id)
    update_capture_mode(run_root, capture_mode)
    local_video = copy_source_into_run(run_root, options["input"])
    update_run_source(run_root, options["input"], local_video)
    result = extract_frames(
        ffmpeg_path=resolved["ffmpeg"], input_video=local_video,
        output_dir=run_root / "frames", logs_dir=run_root / "logs" / "shared",
        fps=4, overwrite=True,
    )
    invalidate_after_extract(run_root)
    update_shared_stage(
        run_root, "extract", "ready", frame_count=result["frame_count"], fps=result["fps"],
        source_file=_rel(run_root, local_video), frames_dir="frames", log=_rel(run_root, result["log"]),
    )
    print("=" * 68); print("Videoto3D V1.3 Frame Extraction")
    print("Run    :", run_id); print("Capture:", capture_mode_label(capture_mode)); print("Input  :", local_video); print("FPS    :", result["fps"])
    print("Frames :", result["frame_count"]); print("Output :", result["output_dir"])
    print("Manifest:", run_root / "run.json"); print("=" * 68)
    print("[READY] Next: python app.py run mask --run {}".format(run_id))
    return 0

def run_mask(runtime, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    frames_dir = run_root / "frames"; masks_dir = run_root / "masks"; segmentation_dir = run_root / "segmentation"
    logs_dir = run_root / "logs" / "shared"
    frame_count = len(list(frames_dir.glob("frame_*.jpg")))
    if frame_count == 0: raise RuntimeError("Run {} has no extracted frames. Run extract first.".format(run_id))
    print("=" * 68); print("Videoto3D V1.3 Object Isolation"); print("Run    :", run_id)
    print("Frames :", frame_count); print("Model  :", runtime["checkpoint"]); print("GPU    :", runtime["detail"]); print("=" * 68)
    box = options.get("box")
    if box is None:
        print("A selection window will open. Drag one box around the target object, then press Enter or Space.")
    else:
        print("Browser ROI:", box)
    report = run_segmentation(
        runtime=runtime, worker_script=ROOT / "scripts" / "sam2_mask_worker.py", frames_dir=frames_dir,
        masks_dir=masks_dir, report_path=segmentation_dir / "report.json",
        log_path=logs_dir / "sam2_mask_worker.log", box=box,
    )
    invalidate_after_mask(run_root)
    update_shared_stage(
        run_root, "mask", "ready", frame_count=report["frame_count"], mask_count=report["mask_count"],
        box_xyxy=report["box_xyxy"], report="segmentation/report.json", masks_dir="masks",
    )
    print("=" * 68); print("Videoto3D V1.3 Mask Result"); print("Run    :", run_id)
    print("Frames :", report["frame_count"]); print("Masks  :", report["mask_count"]); print("Box    :", report["box_xyxy"])
    print("Output :", masks_dir); print("=" * 68); print("[READY] Next: python app.py view masks --run {}".format(run_id))
    return 0

def run_view_masks(runtime, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    validation = validate_masks(run_root / "frames", run_root / "masks")
    result = run_mask_qa_viewer(
        runtime=runtime, viewer_script=ROOT / "scripts" / "mask_qa_viewer.py",
        frames_dir=run_root / "frames", masks_dir=run_root / "masks",
        output_path=run_root / "segmentation" / "mask_qa.jpg",
        log_path=run_root / "logs" / "shared" / "mask_qa_viewer.log", cwd=ROOT,
    )
    print("=" * 68); print("Videoto3D V1.3 Mask QA"); print("Run    :", run_id)
    print("Frames :", validation["frame_count"]); print("Masks  :", validation["mask_count"]); print("QA     :", result["output"])
    print("=" * 68); print("[READY] Next: python app.py run sparse --run {}".format(run_id)); return 0

def run_sparse(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, manifest = _require_run(run_id)
    capture_mode = normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE))
    mask_path = sparse_mask_path(run_root, capture_mode)
    if mask_path is not None:
        validate_masks(run_root / "frames", mask_path)
    result = run_sparse_reconstruction(
        colmap_path=resolved["colmap"], frames_dir=run_root / "frames", colmap_dir=run_root / "colmap",
        logs_dir=run_root / "logs" / "shared", overwrite=True, mask_path=mask_path,
    )
    invalidate_after_sparse(run_root); stats = result["stats"]
    update_shared_stage(
        run_root, "sparse", "ready", frame_count=result["frame_count"],
        registered_images=stats.get("registered_images"), points3D=stats.get("points3D"),
        mean_track_length=stats.get("mean_track_length"), mean_reprojection_error=stats.get("mean_reprojection_error"),
        model=_rel(run_root, result["model"]), database=_rel(run_root, result["database"]),
        capture_mode=capture_mode, mask_guided=(mask_path is not None),
    )
    print("=" * 68); print("Videoto3D V1.3 COLMAP Sparse Reconstruction"); print("Run         :", run_id)
    print("Capture     :", capture_mode_label(capture_mode))
    print("Frames      :", result["frame_count"]); print("Mask mode   :", "SAM2 GUIDED" if mask_path is not None else "DISABLED (full RGB)")
    print("Database    :", result["database"]); print("Model       :", result["model"])
    print("Registered  :", stats.get("registered_images", "-"), "/", result["frame_count"]); print("3D Points   :", stats.get("points3D", "-"))
    print("Track Length:", stats.get("mean_track_length", "-")); print("Reproj Error:", stats.get("mean_reprojection_error", "-")); print("=" * 68)
    print("[READY] Inspect: python app.py view sparse --run {}".format(run_id)); return 0

def run_view_sparse(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id); colmap_dir = run_root / "colmap"
    pid = launch_colmap_gui(
        colmap_path=resolved["colmap"], model_path=colmap_dir / "sparse" / "0",
        database_path=colmap_dir / "database.db", image_path=run_root / "frames", cwd=colmap_dir,
    )
    print("=" * 68); print("Videoto3D V1.3 Shared COLMAP Sparse Viewer"); print("Run   :", run_id); print("PID   :", pid); print("=" * 68)
    return 0

def run_mesh(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    profile = _mesh_profile(options)
    frames_dir = run_root / "frames"; masks_dir = run_root / "masks"; sparse_model = run_root / "colmap" / "sparse" / "0"
    mesh_root = run_root / "mesh"
    validation = validate_masks(frames_dir, masks_dir)
    staged = prepare_openmvs_masks(frames_dir=frames_dir, masks_dir=masks_dir, output_dir=mesh_root / "openmvs_masks")
    print("[READY] SAM2 masks: {} frames / {} masks".format(validation["frame_count"], validation["mask_count"]))
    print("[READY] OpenMVS mask staging:", staged["output_dir"]); print("[INFO] SfM source:", sparse_model)
    result = run_mesh_pipeline(
        colmap_path=resolved["colmap"], openmvs_bin=resolved["openmvs"], frames_dir=frames_dir,
        sparse_model=sparse_model, colmap_dir=mesh_root / "mvs_colmap", openmvs_dir=mesh_root / "openmvs",
        logs_dir=run_root / "logs" / "mesh", overwrite=False, mask_path=mesh_root / "openmvs_masks",
        profile=profile,
    )
    _reset_dirs(mesh_root, ("blender",))
    for stale_glb in (run_root / "output").glob("*.glb"): stale_glb.unlink()
    invalidate_route_stages(run_root, "mesh", ("glb",))
    update_route_stage(run_root, "mesh", "dense", "ready", path=_rel(run_root, result["dense_ply"]))
    update_route_stage(run_root, "mesh", "reconstruct", "ready", path="mesh/openmvs/scene_mesh.ply")
    update_route_stage(run_root, "mesh", "refine", "ready", path=_rel(run_root, result["refined_ply"]))
    update_route_stage(
        run_root, "mesh", "texture", "ready", obj=_rel(run_root, result["obj"]), mtl=_rel(run_root, result["mtl"]),
        textures=[_rel(run_root, item) for item in result["textures"]],
        profile=profile, recipe=_rel(run_root, result["recipe"]) if result.get("recipe") else None,
    )
    print("=" * 68); print("Videoto3D V1.3 Mesh Route"); print("Run         :", run_id); print("OBJ         :", result["obj"])
    print("Textures    :", len(result["textures"])); print("Mesh profile:", profile); print("=" * 68); print("[READY] Next: python app.py run glb --run {}".format(run_id)); return 0

def _validate_glb_name(name):
    name = str(name)
    if Path(name).name != name or not name.lower().endswith(".glb"):
        raise ValueError("--output-name must be a filename ending in .glb, not a path: {}".format(name))
    return name


def run_glb(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id); mesh_root = run_root / "mesh"
    external_output = Path(options["output"]).expanduser() if options.get("output") else None
    if options.get("output_name"): output_name = _validate_glb_name(options["output_name"])
    elif external_output is not None: output_name = _validate_glb_name(external_output.name)
    else: output_name = "{}.glb".format(run_id)
    output_glb = run_root / "output" / output_name
    result = export_obj_to_glb(
        blender_path=resolved["blender"], script_path=ROOT / "scripts" / "blender_export_glb.py",
        input_obj=mesh_root / "openmvs" / "object.obj", output_glb=output_glb,
        working_dir=mesh_root / "blender", log_path=run_root / "logs" / "mesh" / "blender_export_glb.log",
    )
    exported_to = None
    if external_output is not None:
        external_output = external_output.resolve(); external_output.parent.mkdir(parents=True, exist_ok=True)
        if external_output != output_glb.resolve(): shutil.copy2(str(output_glb), str(external_output))
        exported_to = str(external_output)
    update_route_stage(run_root, "mesh", "glb", "ready", path=_rel(run_root, output_glb), size_bytes=result["size_bytes"], exported_to=exported_to)
    _refresh_quality(run_root)
    print("=" * 68); print("Videoto3D V1.3 Blender GLB Export"); print("Run   :", run_id); print("Output:", output_glb)
    if exported_to: print("Export:", exported_to)
    print("Size  : {:.2f} MB".format(result["size_bytes"] / (1024 * 1024))); print("=" * 68)
    print("[READY] View: python app.py view glb --run {}".format(run_id)); return 0

def _positive_int_option(options, name, default):
    value = options.get(name)
    return int(value) if value is not None else int(default)


def _mesh_profile(options):
    values = {}
    for key, default in DEFAULT_MESH_PROFILE.items():
        value = options.get(key)
        values[key] = int(value) if value is not None else int(default)
    return normalize_mesh_profile(values)


def _splat_profile(options):
    return {
        "steps": _positive_int_option(options, "steps", BRUSH_DEFAULT_STEPS),
        "max_splats": _positive_int_option(options, "max_splats", BRUSH_DEFAULT_MAX_SPLATS),
        "max_resolution": _positive_int_option(options, "max_resolution", BRUSH_DEFAULT_MAX_RESOLUTION),
        "foreground_ratio": float(options.get("foreground_ratio", 0.60)),
        "min_foreground_observations": int(options.get("min_foreground_observations", 2)),
    }


def _cleanup_profile(options):
    return {
        "cleanup_ratio": float(options.get("cleanup_ratio", 0.70)),
        "cleanup_min_views": int(options.get("cleanup_min_views", 3)),
    }


def _refresh_quality(run_root):
    try:
        return generate_quality_report(run_root)
    except Exception as exc:
        print("[WARNING] Quality report refresh skipped: {}".format(exc))
        return None


def run_splat_training(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    profile = _splat_profile(options)
    result = run_brush_training(
        brush_path=resolved["brush"], run_root=run_root, run_id=run_id,
        steps=profile["steps"], max_splats=profile["max_splats"], max_resolution=profile["max_resolution"],
        foreground_ratio=profile["foreground_ratio"],
        min_foreground_observations=profile["min_foreground_observations"], min_kept_points=300,
    )
    report = result.get("object_sparse", {})
    final_output = run_root / "output" / (run_id + "_splat.ply")
    if final_output.exists(): final_output.unlink()
    invalidate_route_stages(run_root, "splat", ("cleanup", "ply"))
    update_route_stage(
        run_root, "splat", "training", "ready",
        final_checkpoint=_rel(run_root, result["final_checkpoint"]), final_iteration=result["final_iteration"],
        steps=profile["steps"], max_splats=profile["max_splats"], max_resolution=profile["max_resolution"],
        foreground_ratio=profile["foreground_ratio"],
        min_foreground_observations=profile["min_foreground_observations"],
        object_sparse_report=_rel(run_root, result["object_sparse_report"]),
        source_points=report.get("source_points"), kept_points=report.get("kept_points"), removed_points=report.get("removed_points"),
        dataset=_rel(run_root, result["dataset_root"]), recipe=_rel(run_root, result["recipe"]), log=_rel(run_root, result["log"]),
        raw_path=_rel(run_root, result["raw_ply"]), raw_size_bytes=result["raw_size_bytes"],
    )
    print("=" * 68); print("Videoto3D V1.3 Brush Raw Splat Training"); print("Run        :", run_id)
    print("Object pts : {} / {}".format(report.get("kept_points", "-"), report.get("source_points", "-")))
    print("FG ratio   :", profile["foreground_ratio"]); print("Min FG obs :", profile["min_foreground_observations"])
    print("Steps      :", profile["steps"]); print("Max splats :", profile["max_splats"]); print("Resolution :", profile["max_resolution"])
    print("Final iter :", result["final_iteration"]); print("Raw PLY    :", result["raw_ply"]); print("=" * 68)
    return result


def run_splat_cleanup(options):
    run_id = validate_run_id(options["run"]); run_root, manifest = _require_run(run_id)
    profile = _cleanup_profile(options)
    training = manifest.get("routes", {}).get("splat", {}).get("training", {})
    raw_rel = training.get("raw_path")
    raw_ply = (run_root / raw_rel) if raw_rel else (run_root / "splat" / "raw" / (run_id + "_raw.ply"))
    output_ply = run_root / "output" / (run_id + "_splat.ply")
    cleanup_report = run_root / "splat" / "cleanup_report.json"
    report = cleanup_splat(
        raw_ply=raw_ply, output_ply=output_ply,
        sparse_model=run_root / "colmap" / "sparse" / "0", masks_dir=run_root / "masks",
        report_path=cleanup_report, foreground_ratio=profile["cleanup_ratio"],
        min_views=profile["cleanup_min_views"], min_kept_splats=100,
    )
    update_route_stage(
        run_root, "splat", "cleanup", "ready",
        report=_rel(run_root, cleanup_report), raw_path=_rel(run_root, raw_ply),
        raw_splats=report["raw_splats"], clean_splats=report["clean_splats"], removed_splats=report["removed_splats"],
        removal_ratio=report["removal_ratio"], foreground_ratio=profile["cleanup_ratio"], min_views=profile["cleanup_min_views"],
        mean_valid_views=report.get("mean_valid_views"), mean_foreground_support=report.get("mean_foreground_support"),
    )
    update_route_stage(
        run_root, "splat", "ply", "ready", path=_rel(run_root, output_ply), size_bytes=output_ply.stat().st_size,
    )
    _refresh_quality(run_root)
    print("=" * 68); print("Videoto3D V1.3 Splat Cleanup"); print("Run        :", run_id)
    print("Raw splats :", report["raw_splats"]); print("Clean      :", report["clean_splats"])
    print("Removed    : {} ({:.1f}%)".format(report["removed_splats"], report["removal_ratio"] * 100.0))
    print("Mask vote  : ratio >= {} / valid views >= {}".format(profile["cleanup_ratio"], profile["cleanup_min_views"]))
    print("Final PLY  :", output_ply); print("Report     :", cleanup_report); print("=" * 68)
    return 0


def run_splat(resolved, options):
    run_splat_training(resolved, options)
    return run_splat_cleanup(options)


def _resolve_splat_asset(options):
    if options.get("path"): return Path(options["path"]).expanduser().resolve(), None
    run_id = validate_run_id(options["run"]); run_root, manifest = _require_run(run_id)
    entry = manifest.get("routes", {}).get("splat", {}).get("ply", {}); rel = entry.get("path")
    if not rel: raise RuntimeError("Run {} has no V0.11 Splat PLY recorded. Run splat first.".format(run_id))
    return run_root / rel, run_root

def run_view_splat(resolved, options):
    asset, run_root = _resolve_splat_asset(options)
    pid = launch_brush_viewer(brush_path=resolved["brush"], splat_path=asset, working_dir=(run_root / "splat") if run_root else asset.parent)
    print("[READY] Brush Splat Viewer PID {}: {}".format(pid, asset)); print("[INFO] Viewer runs detached; closing it does not require Ctrl+C."); return 0

def run_view_splat_init(resolved, options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    model = run_root / "splat" / "dataset" / "sparse" / "0"
    report = run_root / "splat" / "object_sparse_report.json"
    if not report.exists():
        raise RuntimeError("Object-only sparse initialization not found. Run splat once (or route splat) to stage it.")
    pid = launch_colmap_gui(
        colmap_path=resolved["colmap"], model_path=model, database_path=run_root / "colmap" / "database.db",
        image_path=run_root / "frames", cwd=run_root / "splat",
    )
    print("[READY] Object-only Splat Init Viewer PID {}: {}".format(pid, model)); return 0


def _resolve_view_asset(options, kind):
    if options.get("path"): return Path(options["path"]).expanduser().resolve(), None
    run_id = validate_run_id(options["run"]); run_root, manifest = _require_run(run_id)
    if kind == "mesh": return run_root / "mesh" / "openmvs" / "object.obj", run_root
    glb_entry = manifest.get("routes", {}).get("mesh", {}).get("glb", {}); rel = glb_entry.get("path")
    if not rel: raise RuntimeError("Run {} has no GLB recorded. Run glb first.".format(run_id))
    return run_root / rel, run_root

def run_view_mesh(resolved, options):
    asset, run_root = _resolve_view_asset(options, "mesh")
    pid = launch_asset_viewer(
        blender_path=resolved["blender"], script_path=ROOT / "scripts" / "blender_view_asset.py", input_asset=asset,
        working_dir=(run_root / "mesh" / "blender") if run_root else asset.parent,
    )
    print("[READY] Blender Mesh Viewer PID {}: {}".format(pid, asset)); return 0

def run_view_glb(resolved, options):
    asset, run_root = _resolve_view_asset(options, "glb")
    pid = launch_asset_viewer(
        blender_path=resolved["blender"], script_path=ROOT / "scripts" / "blender_view_asset.py", input_asset=asset,
        working_dir=(run_root / "mesh" / "blender") if run_root else asset.parent,
    )
    print("[READY] Blender GLB Viewer PID {}: {}".format(pid, asset)); print("[INFO] Viewer automatically switches to Material Preview."); return 0

def run_runs_list():
    summaries = list_run_summaries(WORKSPACE / "runs")
    if not summaries: print("No runs found in {}".format(WORKSPACE / "runs")); return 0
    print("RUN ID              SHARED          MESH ROUTE       SPLAT ROUTE")
    print("-" * 72)
    for item in summaries:
        print("{:<19} {:<15} {:<16} {:<16}".format(item["run_id"], item["shared_status"], item["mesh_status"], item["splat_status"]))
    return 0

def run_runs_show(options):
    run_id = validate_run_id(options["run"]); run_root, manifest = _require_run(run_id)
    def st(section, stage): return section.get(stage, {}).get("status", "pending")
    shared = manifest.get("shared", {}); mesh = manifest.get("routes", {}).get("mesh", {}); splat = manifest.get("routes", {}).get("splat", {})
    print("=" * 68); print("Videoto3D Run:", run_id); print("Root     :", run_root); print("Created  :", manifest.get("created_at", "-")); print("Updated  :", manifest.get("updated_at", "-"))
    source = manifest.get("source", {}); print("Source   :", source.get("local_file", "-")); print("Original :", source.get("original_input", "-")); print("Capture  :", capture_mode_label(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE)))
    print(); print("Shared")
    for stage in ("extract", "mask", "sparse"):
        entry = shared.get(stage, {}); suffix = ""
        if stage == "extract" and entry.get("frame_count") is not None: suffix = "  {} frames".format(entry.get("frame_count"))
        if stage == "mask" and entry.get("mask_count") is not None: suffix = "  {} masks".format(entry.get("mask_count"))
        if stage == "sparse" and entry.get("registered_images") is not None: suffix = "  {} registered / {} points".format(entry.get("registered_images"), entry.get("points3D", "-"))
        print("  {:9}: {}{}".format(stage, st(shared, stage), suffix))
    print(); print("Mesh Route")
    reconstruct_status = "ready" if mesh.get("texture", {}).get("status") == "ready" else "pending"
    if reconstruct_status != "ready" and (run_root / "mesh" / "openmvs" / "object.obj").exists(): reconstruct_status = "cached"
    print("  reconstruct: {}".format(reconstruct_status))
    print("  glb        : {}".format(st(mesh, "glb")))
    glb = mesh.get("glb", {}).get("path")
    if glb: print("               {}".format(run_root / glb))
    print(); print("Splat Route")
    training = splat.get("training", {}); cleanup = splat.get("cleanup", {}); ply = splat.get("ply", {})
    train_extra = "  {} steps".format(training.get("steps")) if training.get("steps") is not None else ""
    clean_extra = ""
    if cleanup.get("clean_splats") is not None and cleanup.get("raw_splats") is not None:
        clean_extra = "  {} / {} splats".format(cleanup.get("clean_splats"), cleanup.get("raw_splats"))
    print("  train      : {}{}".format(st(splat, "training"), train_extra))
    print("  cleanup    : {}{}".format(st(splat, "cleanup"), clean_extra))
    print("  ply        : {}".format(st(splat, "ply")))
    if ply.get("path"): print("               {}".format(run_root / ply["path"]))
    print(); print("Quality  : python app.py quality --run {}".format(run_id))
    print("=" * 68); return 0


def _route_shared_ready(manifest, stage):
    return shared_stage_status(manifest, stage) == "ready"


def _route_toolset(names):
    ok, resolved = check_required_tools(tuple(names))
    if not ok: raise RuntimeError("Required route tools are not ready: {}".format(", ".join(names)))
    return resolved


def _route_prepare_shared(options):
    run_id = validate_run_id(options["run"]); run_root = resolve_run_root(run_id); input_path = options.get("input")
    requested_capture_mode = (
        normalize_capture_mode(options.get("capture_mode"))
        if options.get("capture_mode") is not None else None
    )
    if not (run_root / "run.json").exists() and not input_path:
        raise RuntimeError("New Run {} requires --input <video>.".format(run_id))
    if input_path:
        print("[ROUTE][RUN ] shared.extract (input supplied)")
        extract_options = {"run": run_id, "input": input_path}
        if requested_capture_mode is not None:
            extract_options["capture_mode"] = requested_capture_mode
        run_extract(_route_toolset(("ffmpeg",)), extract_options)
    run_root, manifest = _require_run(run_id)
    current_capture_mode = normalize_capture_mode(manifest.get("capture_mode", DEFAULT_CAPTURE_MODE))
    if requested_capture_mode is not None and requested_capture_mode != current_capture_mode:
        raise RuntimeError(
            "Run {} is capture_mode={!r}, requested {!r}. Re-run with --input so Shared data can be rebuilt safely."
            .format(run_id, current_capture_mode, requested_capture_mode)
        )
    print("[ROUTE][INFO] capture_mode={}".format(current_capture_mode))
    if _route_shared_ready(manifest, "extract"): print("[ROUTE][SKIP] shared.extract READY")
    else: raise RuntimeError("Shared extract is not ready; provide --input <video>.")
    manifest = load_run_manifest(run_root)
    if _route_shared_ready(manifest, "mask"):
        print("[ROUTE][SKIP] shared.mask READY")
    else:
        print("[ROUTE][RUN ] shared.mask")
        ok, runtime = check_segmentation_environment()
        if not ok: raise RuntimeError("Segmentation runtime not ready")
        run_mask(runtime, {"run": run_id})
    manifest = load_run_manifest(run_root)
    if _route_shared_ready(manifest, "sparse"):
        print("[ROUTE][SKIP] shared.sparse READY")
    else:
        print("[ROUTE][RUN ] shared.sparse")
        run_sparse(_route_toolset(("colmap",)), {"run": run_id})
    return run_root, load_run_manifest(run_root)


def run_route_mesh(options):
    run_id = validate_run_id(options["run"])
    print(); print("========== Shared → Mesh Route ==========")
    run_root, manifest = _route_prepare_shared(options)
    desired_profile = _mesh_profile(options)
    mesh = manifest.get("routes", {}).get("mesh", {})
    openmvs_dir = run_root / "mesh" / "openmvs"
    stored_profile = mesh.get("texture", {}).get("profile")
    recipe_ok = False
    if stored_profile:
        try:
            recipe_ok = normalize_mesh_profile(stored_profile) == desired_profile
        except (TypeError, ValueError):
            recipe_ok = False
    elif mesh.get("texture", {}).get("status") == "ready":
        # Pre-V1.1.2 successful Mesh runs used exactly these defaults.
        recipe_ok = desired_profile == normalize_mesh_profile(DEFAULT_MESH_PROFILE)
    else:
        recipe_ok = mesh_recipe_matches(openmvs_dir, desired_profile)
    if mesh.get("texture", {}).get("status") == "ready" and (openmvs_dir / "object.obj").exists() and recipe_ok:
        print("[ROUTE][SKIP] mesh.texture READY (Mesh recipe matches)")
    else:
        print("[ROUTE][RUN ] Mesh Route: recipe-aware OpenMVS")
        mesh_options = {"run": run_id}
        mesh_options.update({key: str(value) for key, value in desired_profile.items()})
        run_mesh(_route_toolset(("colmap", "openmvs")), mesh_options)
    manifest = load_run_manifest(run_root); force_glb = bool(options.get("output_name") or options.get("output"))
    if manifest.get("routes", {}).get("mesh", {}).get("glb", {}).get("status") == "ready" and not force_glb:
        print("[ROUTE][SKIP] mesh.glb READY")
    else:
        print("[ROUTE][RUN ] mesh.glb")
        glb_options = {"run": run_id, "output_name": options.get("output_name"), "output": options.get("output")}
        run_glb(_route_toolset(("blender",)), glb_options)
    print("[READY] Mesh Route complete: python app.py view glb --run {}".format(run_id)); return 0


def run_route_splat(options):
    run_id = validate_run_id(options["run"])
    print(); print("========== Shared → Splat Route ==========")
    run_root, manifest = _route_prepare_shared(options)
    desired = _splat_profile(options); cleanup_desired = _cleanup_profile(options)
    splat = manifest.get("routes", {}).get("splat", {}); training = splat.get("training", {})
    raw_rel = training.get("raw_path"); raw_path = run_root / raw_rel if raw_rel else run_root / "splat" / "raw" / (run_id + "_raw.ply")
    training_matches = (
        training.get("status") == "ready" and raw_path.exists()
        and int(training.get("steps", -1)) == desired["steps"]
        and int(training.get("max_splats", -1)) == desired["max_splats"]
        and int(training.get("max_resolution", -1)) == desired["max_resolution"]
        and abs(float(training.get("foreground_ratio", -1.0)) - desired["foreground_ratio"]) < 1e-9
        and int(training.get("min_foreground_observations", -1)) == desired["min_foreground_observations"]
    )
    if training_matches:
        print("[ROUTE][SKIP] splat.train READY (Brush recipe matches)")
    else:
        print("[ROUTE][RUN ] object-only sparse → Brush raw PLY")
        train_options = {"run": run_id}; train_options.update({key: str(value) for key, value in desired.items()})
        run_splat_training(_route_toolset(("brush",)), train_options)
    manifest = load_run_manifest(run_root); splat = manifest.get("routes", {}).get("splat", {}); cleanup = splat.get("cleanup", {})
    final_ply = run_root / "output" / (run_id + "_splat.ply")
    cleanup_matches = (
        cleanup.get("status") == "ready" and final_ply.exists()
        and abs(float(cleanup.get("foreground_ratio", -1.0)) - cleanup_desired["cleanup_ratio"]) < 1e-9
        and int(cleanup.get("min_views", -1)) == cleanup_desired["cleanup_min_views"]
    )
    if cleanup_matches and splat.get("ply", {}).get("status") == "ready":
        print("[ROUTE][SKIP] splat.cleanup READY (cleanup recipe matches)")
    else:
        print("[ROUTE][RUN ] SAM2/COLMAP multi-view Splat Cleanup")
        clean_options = {"run": run_id, "cleanup_ratio": str(cleanup_desired["cleanup_ratio"]), "cleanup_min_views": str(cleanup_desired["cleanup_min_views"])}
        run_splat_cleanup(clean_options)
    _refresh_quality(run_root)
    print("[READY] Splat Route complete: python app.py view splat --run {}".format(run_id)); return 0


def run_quality(options):
    run_id = validate_run_id(options["run"]); run_root, _ = _require_run(run_id)
    generate_quality_report(run_root)
    report_path = run_root / "quality" / "report.md"
    print(report_path.read_text(encoding="utf-8"))
    print("[READY] Quality report: {}".format(report_path))
    return 0


def check_segmentation_environment():
    print("=" * 68)
    print("Videoto3D Segmentation Environment Check")
    print("Root   :", ROOT)
    print(
        "Main Python:",
        sys.version.split()[0],
        sys.executable,
    )
    print("=" * 68)

    try:
        runtime = resolve_segmentation_runtime(
            ROOT
        )
    except RuntimeError as exc:
        print(
            "[ERROR] Segmentation runtime not ready."
        )
        print(
            "        {}".format(exc)
        )
        print(
            "Setup guide:",
            ROOT / "docs" / "segmentation-windows.md",
        )
        return False, None

    print(
        "[READY] segmentation {}".format(
            runtime["python"]
        )
    )
    print(
        "        {}".format(
            runtime["detail"]
        )
    )
    print("=" * 68)

    return True, runtime


def required_tools_for_key(key):
    return tuple(command_spec(key)["tools"])


def print_legacy_command_error(parsed):
    print("[ERROR] 命令格式已在 Videoto3D V1.0 更新。")
    print("旧命令：python app.py {}".format(parsed["legacy"]))
    print("新命令：{}".format(parsed["replacement"]))
    print("查看全部命令：python app.py --help 或阅读 README.md")



def run_env_status():
    print("ENVIRONMENT         STATUS     PATH")
    print("-" * 72)
    for name in ("core", "seg", "gui"):
        item = environment_status(ROOT, name)
        print("{:<19} {:<10} {}".format(name, item["status"], item["prefix"]))
    return 0


def run_env_repair(options):
    name = options["environment"]
    if name == "core":
        current = os.path.normcase(os.path.abspath(sys.executable))
        target = os.path.normcase(os.path.abspath(str(environment_python(ROOT, "core"))))
        if current == target:
            raise RuntimeError("core repair 必须从项目外层 Python 启动：python app.py env repair core")
    repair_environment(ROOT, name)
    return 0


def main():
    parsed = parse_cli_args(sys.argv[1:])

    if parsed["kind"] == "help":
        print_cli_help()
        return 0

    if parsed["kind"] == "legacy":
        print_legacy_command_error(parsed)
        return 2

    if parsed["kind"] == "error":
        print("[ERROR] {}".format(parsed["message"]))
        print_cli_help()
        return 2

    key = parsed["key"]
    options = parsed.get("options", {})
    spec = command_spec(key)
    print_command_annotation(spec, parsed.get("options", {}))

    if key == "doctor":
        ok, resolved = check_environment()
        runtime = None
    elif key in ("run.mask", "view.masks"):
        ok, runtime = check_segmentation_environment()
        resolved = {}
    elif key in ("runs.list", "runs.show", "route.mesh", "route.splat", "quality", "gui", "env.status", "env.repair"):
        ok, resolved, runtime = True, {}, None
    else:
        ok, resolved = check_required_tools(required_tools_for_key(key))
        runtime = None

    if not ok:
        return 1

    if key == "doctor":
        print("[READY] Videoto3D 全部环境检查完成。")
        return 0
    try:
        if key == "run.extract":
            return run_extract(resolved, options)
        if key == "run.mask":
            return run_mask(runtime, options)
        if key == "view.masks":
            return run_view_masks(runtime, options)
        if key == "run.sparse":
            return run_sparse(resolved, options)
        if key == "view.sparse":
            return run_view_sparse(resolved, options)
        if key == "run.mesh":
            return run_mesh(resolved, options)
        if key == "view.mesh":
            return run_view_mesh(resolved, options)
        if key == "run.glb":
            return run_glb(resolved, options)
        if key == "view.glb":
            return run_view_glb(resolved, options)
        if key == "run.splat":
            return run_splat(resolved, options)
        if key == "view.splat-init":
            return run_view_splat_init(resolved, options)
        if key == "view.splat":
            return run_view_splat(resolved, options)
        if key == "quality":
            return run_quality(options)
        if key == "gui":
            return run_gui_server(ROOT)
        if key == "env.status":
            return run_env_status()
        if key == "env.repair":
            return run_env_repair(options)
        if key == "route.mesh":
            return run_route_mesh(options)
        if key == "route.splat":
            return run_route_splat(options)
        if key == "runs.list":
            return run_runs_list()
        if key == "runs.show":
            return run_runs_show(options)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print("[ERROR] {}".format(exc))
        return 1

    raise RuntimeError("Unhandled canonical command: {}".format(key))


if __name__ == "__main__":
    sys.exit(main())
