import json
import os
import shutil
import subprocess
from pathlib import Path


TEXTURE_RECIPE_VERSION = "openmvs-2.4.0-seam-leveling-off-v1"
TEXTURE_RECIPE_FILE = "texture_recipe.json"
MESH_RECIPE_VERSION = "videoto3d-mesh-profile-v1"
MESH_RECIPE_FILE = "mesh_recipe.json"

DEFAULT_MESH_PROFILE = {
    "undistort_max_image_size": 2000,
    "dense_resolution_level": 0,
    "dense_number_views": 0,
    "dense_max_threads": 0,
    "refine_resolution_level": 1,
}


def normalize_mesh_profile(profile=None):
    values = dict(DEFAULT_MESH_PROFILE)
    if profile:
        for key in values:
            if key in profile and profile[key] is not None:
                values[key] = int(profile[key])
    if values["undistort_max_image_size"] <= 0:
        raise ValueError("undistort_max_image_size must be > 0")
    if values["dense_resolution_level"] < 0:
        raise ValueError("dense_resolution_level must be >= 0")
    if values["dense_number_views"] < 0:
        raise ValueError("dense_number_views must be >= 0")
    if values["dense_max_threads"] < 0:
        raise ValueError("dense_max_threads must be >= 0")
    if values["refine_resolution_level"] < 0:
        raise ValueError("refine_resolution_level must be >= 0")
    return values


def mesh_recipe_change_stage(current, desired):
    current = normalize_mesh_profile(current)
    desired = normalize_mesh_profile(desired)
    if current["undistort_max_image_size"] != desired["undistort_max_image_size"]:
        return "interface"
    for key in ("dense_resolution_level", "dense_number_views", "dense_max_threads"):
        if current[key] != desired[key]:
            return "dense"
    if current["refine_resolution_level"] != desired["refine_resolution_level"]:
        return "refine"
    return None


def _mesh_recipe_path(openmvs_dir):
    return Path(openmvs_dir) / MESH_RECIPE_FILE


def read_mesh_recipe(openmvs_dir):
    path = _mesh_recipe_path(openmvs_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    profile = data.get("profile") if isinstance(data, dict) else None
    try:
        return normalize_mesh_profile(profile)
    except (TypeError, ValueError):
        return None


def write_mesh_recipe(openmvs_dir, profile):
    path = _mesh_recipe_path(openmvs_dir)
    payload = {
        "version": MESH_RECIPE_VERSION,
        "profile": normalize_mesh_profile(profile),
        "texture_workaround": {
            "bug": "BUG-0001",
            "global_seam_leveling": 0,
            "local_seam_leveling": 0,
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def mesh_recipe_matches(openmvs_dir, desired_profile):
    current = read_mesh_recipe(openmvs_dir)
    if current is None:
        # Preserve successful pre-V1.1.2 output as legacy defaults.
        if texture_outputs_ready(openmvs_dir):
            current = dict(DEFAULT_MESH_PROFILE)
        else:
            return False
    return mesh_recipe_change_stage(current, desired_profile) is None


def build_image_undistorter_args(
    image_path,
    input_model,
    output_path,
    profile=None,
):
    profile = normalize_mesh_profile(profile)
    return [
        "image_undistorter",
        "--image_path", str(Path(image_path)),
        "--input_path", str(Path(input_model)),
        "--output_path", str(Path(output_path)),
        "--output_type", "COLMAP",
        "--max_image_size", str(profile["undistort_max_image_size"]),
    ]


def _build_colmap_command(colmap_path, args):
    colmap_path = Path(colmap_path)

    if colmap_path.suffix.lower() in (".bat", ".cmd"):
        return [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(colmap_path),
        ] + list(args)

    return [str(colmap_path)] + list(args)


def build_interface_colmap_args(
    undistorted_root,
    undistorted_images,
    openmvs_dir,
):
    return [
        "--working-folder", str(Path(openmvs_dir)),
        "--input-file", str(Path(undistorted_root)),
        "--image-folder", str(Path(undistorted_images)),
        "--output-file", str(Path(openmvs_dir) / "scene.mvs"),
    ]


def build_densify_args(openmvs_dir, safe_mode=False, mask_path=None, profile=None):
    explicit_profile = profile is not None
    profile = normalize_mesh_profile(profile)
    args = [
        "--working-folder", str(Path(openmvs_dir)),
        "--input-file", str(Path(openmvs_dir) / "scene.mvs"),
        "--output-file", str(Path(openmvs_dir) / "scene_dense.mvs"),
        "--archive-type", "-1",
    ]

    if mask_path is not None:
        args.extend(
            [
                "--mask-path", str(Path(mask_path)),
                "--ignore-mask-label", "0",
            ]
        )

    if safe_mode:
        args.extend(
            [
                "--resolution-level", "1",
                "--number-views", "8",
                "--max-threads", choose_densify_thread_count(),
            ]
        )
    elif explicit_profile:
        args.extend(["--resolution-level", str(profile["dense_resolution_level"])])
        if profile["dense_number_views"] > 0:
            args.extend(["--number-views", str(profile["dense_number_views"])])
        if profile["dense_max_threads"] > 0:
            args.extend(["--max-threads", str(profile["dense_max_threads"])])

    return args


def is_retryable_densify_exit_code(returncode):
    # Windows STATUS_ACCESS_VIOLATION may surface as unsigned
    # 3221225477 or signed -1073741819.
    return returncode in (
        3221225477,
        -1073741819,
    )




def choose_densify_thread_count():
    """Return the conservative Windows retry thread count.

    On the target high-core Windows machine, manual `--max-threads 1` was the
    configuration that completed dense fusion and saved both required outputs.
    The first attempt still uses OpenMVS defaults; this policy is only for the
    crash-recovery retry.
    """
    cpu = os.cpu_count() or 4

    if cpu >= 24:
        return "1"
    if cpu >= 12:
        return "2"
    if cpu >= 8:
        return "2"
    return "1"


def _nonempty_file(path, min_size=1):
    path = Path(path)
    return path.exists() and path.is_file() and path.stat().st_size >= min_size


def undistorted_outputs_ready(undistorted_dir):
    undistorted_dir = Path(undistorted_dir)
    sparse_dir = undistorted_dir / "sparse"
    images_dir = undistorted_dir / "images"
    required = (
        sparse_dir / "cameras.bin",
        sparse_dir / "images.bin",
        sparse_dir / "points3D.bin",
    )
    return (
        all(_nonempty_file(path) for path in required)
        and images_dir.exists()
        and any(path.is_file() for path in images_dir.iterdir())
    )


def scene_output_ready(openmvs_dir):
    return _nonempty_file(Path(openmvs_dir) / "scene.mvs")


def dense_outputs_ready(openmvs_dir):
    openmvs_dir = Path(openmvs_dir)

    dense_mvs = openmvs_dir / "scene_dense.mvs"
    dense_ply = openmvs_dir / "scene_dense.ply"

    return (
        _nonempty_file(dense_mvs)
        and _nonempty_file(dense_ply, min_size=1024)
    )


def mesh_output_ready(openmvs_dir):
    return _nonempty_file(Path(openmvs_dir) / "scene_mesh.ply", min_size=1024)


def refined_output_ready(openmvs_dir):
    return _nonempty_file(Path(openmvs_dir) / "scene_refined.ply", min_size=1024)


def _texture_recipe_matches(openmvs_dir):
    recipe_path = Path(openmvs_dir) / TEXTURE_RECIPE_FILE
    if not recipe_path.is_file():
        return False
    try:
        data = json.loads(recipe_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return data.get("version") == TEXTURE_RECIPE_VERSION


def _write_texture_recipe(openmvs_dir, masked):
    recipe_path = Path(openmvs_dir) / TEXTURE_RECIPE_FILE
    payload = {
        "version": TEXTURE_RECIPE_VERSION,
        "bug": "BUG-0001",
        "upstream": "https://github.com/cdcseacave/openMVS/issues/1251",
        "masked": bool(masked),
        "texture_flags": {
            "ignore_mask_label": 0 if masked else None,
            "global_seam_leveling": 0,
            "local_seam_leveling": 0,
        },
    }
    recipe_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def texture_outputs_ready(openmvs_dir):
    outputs = _find_texture_outputs(openmvs_dir)
    return (
        _texture_recipe_matches(openmvs_dir)
        and _nonempty_file(outputs["obj"])
        and _nonempty_file(outputs["mtl"])
        and any(_nonempty_file(path) for path in outputs["textures"])
    )


def _remove_paths(paths):
    for path in paths:
        path = Path(path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _invalidate_from(openmvs_dir, stage):
    openmvs_dir = Path(openmvs_dir)
    stage_paths = {
        "interface": (
            openmvs_dir / "scene.mvs",
            openmvs_dir / "scene_dense.mvs",
            openmvs_dir / "scene_dense.ply",
            openmvs_dir / "scene_mesh.ply",
            openmvs_dir / "scene_refined.ply",
            openmvs_dir / "object.obj",
            openmvs_dir / "object.mtl",
        ),
        "dense": (
            openmvs_dir / "scene_dense.mvs",
            openmvs_dir / "scene_dense.ply",
            openmvs_dir / "scene_mesh.ply",
            openmvs_dir / "scene_refined.ply",
            openmvs_dir / "object.obj",
            openmvs_dir / "object.mtl",
        ),
        "mesh": (
            openmvs_dir / "scene_mesh.ply",
            openmvs_dir / "scene_refined.ply",
            openmvs_dir / "object.obj",
            openmvs_dir / "object.mtl",
        ),
        "refine": (
            openmvs_dir / "scene_refined.ply",
            openmvs_dir / "object.obj",
            openmvs_dir / "object.mtl",
        ),
        "texture": (
            openmvs_dir / "object.obj",
            openmvs_dir / "object.mtl",
        ),
    }
    paths = list(stage_paths[stage])
    if stage in ("interface", "dense", "mesh", "refine", "texture"):
        paths.extend(openmvs_dir.glob("*map_Kd*"))
        paths.append(openmvs_dir / TEXTURE_RECIPE_FILE)
    _remove_paths(paths)


def _prepare_mesh_recipe(undistorted_dir, openmvs_dir, desired_profile):
    desired = normalize_mesh_profile(desired_profile)
    current = read_mesh_recipe(openmvs_dir)
    if current is None:
        has_legacy_cache = (
            undistorted_outputs_ready(undistorted_dir)
            or scene_output_ready(openmvs_dir)
            or dense_outputs_ready(openmvs_dir)
            or refined_output_ready(openmvs_dir)
            or texture_outputs_ready(openmvs_dir)
        )
        if has_legacy_cache:
            current = dict(DEFAULT_MESH_PROFILE)
    if current is None:
        return None
    stage = mesh_recipe_change_stage(current, desired)
    if stage == "interface":
        if Path(undistorted_dir).exists():
            shutil.rmtree(undistorted_dir)
        _invalidate_from(openmvs_dir, "interface")
    elif stage in ("dense", "refine"):
        _invalidate_from(openmvs_dir, stage)
    return stage


def build_reconstruct_mesh_args(openmvs_dir):
    return [
        "--working-folder", str(Path(openmvs_dir)),
        "--input-file", str(Path(openmvs_dir) / "scene_dense.mvs"),
        "--output-file", str(Path(openmvs_dir) / "scene_mesh.ply"),
    ]


def build_refine_mesh_args(openmvs_dir, profile=None):
    profile = normalize_mesh_profile(profile)
    return [
        "--working-folder", str(Path(openmvs_dir)),
        "--input-file", str(Path(openmvs_dir) / "scene_dense.mvs"),
        "--mesh-file", str(Path(openmvs_dir) / "scene_mesh.ply"),
        "--output-file", str(Path(openmvs_dir) / "scene_refined.ply"),
        "--resolution-level", str(profile["refine_resolution_level"]),
    ]


def build_texture_mesh_args(openmvs_dir, masked=False):
    args = [
        "--working-folder", str(Path(openmvs_dir)),
        "--input-file", str(Path(openmvs_dir) / "scene_dense.mvs"),
        "--mesh-file", str(Path(openmvs_dir) / "scene_refined.ply"),
        "--output-file", str(Path(openmvs_dir) / "object.obj"),
        "--export-type", "obj",
    ]

    if masked:
        args.extend(["--ignore-mask-label", "0"])

    # OpenMVS 2.4.0 regression (upstream issue #1251): seam leveling
    # can turn valid texture patches black. Keep it disabled until the
    # runtime is upgraded to a build containing the upstream sampler fix.
    args.extend(
        [
            "--global-seam-leveling", "0",
            "--local-seam-leveling", "0",
        ]
    )

    return args


def _run_process(
    executable,
    args,
    log_path,
    cwd,
    accepted_exit_codes=(0,),
    raise_on_error=True,
):
    executable = Path(executable)
    log_path = Path(log_path)

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        str(executable),
    ] + list(args)

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if (
        raise_on_error
        and result.returncode not in accepted_exit_codes
    ):
        raise RuntimeError(
            "{} failed with exit code {}. See {}".format(
                executable.name,
                result.returncode,
                log_path,
            )
        )

    return result.returncode


def _run_colmap(
    colmap_path,
    args,
    log_path,
    cwd,
):
    log_path = Path(log_path)
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = _build_colmap_command(
        colmap_path,
        args,
    )

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        raise RuntimeError(
            "COLMAP {} failed with exit code {}. See {}".format(
                args[0],
                result.returncode,
                log_path,
            )
        )

    return result.returncode


def _require_files(paths, stage_name):
    missing = [
        str(Path(path))
        for path in paths
        if not Path(path).exists()
    ]

    if missing:
        raise RuntimeError(
            "{} completed but required output is missing: {}".format(
                stage_name,
                ", ".join(missing),
            )
        )


def _find_texture_outputs(openmvs_dir):
    openmvs_dir = Path(openmvs_dir)

    return {
        "obj": str(openmvs_dir / "object.obj"),
        "mtl": str(openmvs_dir / "object.mtl"),
        "textures": [
            str(path)
            for path in sorted(
                openmvs_dir.glob("*map_Kd*")
            )
        ],
    }


def run_mesh_pipeline(
    colmap_path,
    openmvs_bin,
    frames_dir,
    sparse_model,
    colmap_dir,
    openmvs_dir,
    logs_dir,
    overwrite=True,
    mask_path=None,
    profile=None,
):
    colmap_path = Path(colmap_path)
    openmvs_bin = Path(openmvs_bin)
    frames_dir = Path(frames_dir)
    sparse_model = Path(sparse_model)
    colmap_dir = Path(colmap_dir)
    openmvs_dir = Path(openmvs_dir)
    logs_dir = Path(logs_dir)
    mask_path = Path(mask_path) if mask_path is not None else None
    profile = normalize_mesh_profile(profile)

    if not colmap_path.exists():
        raise FileNotFoundError(
            "COLMAP not found: {}".format(colmap_path)
        )

    if mask_path is not None and not mask_path.exists():
        raise FileNotFoundError(
            "OpenMVS mask directory not found: {}".format(mask_path)
        )

    required_sparse = (
        sparse_model / "cameras.bin",
        sparse_model / "images.bin",
        sparse_model / "points3D.bin",
    )
    _require_files(
        required_sparse,
        "Sparse reconstruction",
    )

    required_openmvs_tools = (
        "InterfaceCOLMAP.exe",
        "DensifyPointCloud.exe",
        "ReconstructMesh.exe",
        "RefineMesh.exe",
        "TextureMesh.exe",
    )

    for executable in required_openmvs_tools:
        if not (openmvs_bin / executable).exists():
            raise FileNotFoundError(
                "OpenMVS tool not found: {}".format(
                    openmvs_bin / executable
                )
            )

    undistorted_dir = colmap_dir / "undistorted"

    recipe_change_stage = None
    if not overwrite:
        recipe_change_stage = _prepare_mesh_recipe(
            undistorted_dir=undistorted_dir,
            openmvs_dir=openmvs_dir,
            desired_profile=profile,
        )
        if recipe_change_stage:
            print("[RECIPE] Mesh settings changed; invalidating from {}.".format(recipe_change_stage))

    if overwrite:
        if undistorted_dir.exists():
            shutil.rmtree(undistorted_dir)

        if openmvs_dir.exists():
            shutil.rmtree(openmvs_dir)

    undistorted_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    openmvs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    logs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("[1/6] COLMAP image undistortion...")
    if not overwrite and undistorted_outputs_ready(undistorted_dir):
        print("[CACHE] Existing undistorted COLMAP workspace detected.")
        print("[SKIP] COLMAP image_undistorter")
    else:
        if undistorted_dir.exists():
            shutil.rmtree(undistorted_dir)
        undistorted_dir.mkdir(parents=True, exist_ok=True)
        _invalidate_from(openmvs_dir, "interface")
        _run_colmap(
            colmap_path=colmap_path,
            args=build_image_undistorter_args(
                image_path=frames_dir,
                input_model=sparse_model,
                output_path=undistorted_dir,
                profile=profile,
            ),
            log_path=logs_dir / "colmap_image_undistorter.log",
            cwd=colmap_dir,
        )

    undistorted_sparse = undistorted_dir / "sparse"
    undistorted_images = undistorted_dir / "images"

    _require_files(
        (
            undistorted_sparse / "cameras.bin",
            undistorted_sparse / "images.bin",
            undistorted_sparse / "points3D.bin",
        ),
        "COLMAP image undistorter",
    )

    if not undistorted_images.exists():
        raise RuntimeError(
            "COLMAP image undistorter did not create {}".format(
                undistorted_images
            )
        )

    print("[2/6] OpenMVS InterfaceCOLMAP...")
    if not overwrite and scene_output_ready(openmvs_dir):
        print("[CACHE] Existing OpenMVS scene detected.")
        print("[SKIP] InterfaceCOLMAP")
    else:
        _invalidate_from(openmvs_dir, "interface")
        _run_process(
            executable=openmvs_bin / "InterfaceCOLMAP.exe",
            args=build_interface_colmap_args(
                undistorted_root=undistorted_dir,
                undistorted_images=undistorted_images,
                openmvs_dir=openmvs_dir,
            ),
            log_path=logs_dir / "openmvs_interface_colmap.log",
            cwd=openmvs_dir,
        )
    _require_files(
        (openmvs_dir / "scene.mvs",),
        "InterfaceCOLMAP",
    )

    print("[3/6] OpenMVS dense point cloud...")

    densify_log = logs_dir / "openmvs_densify.log"

    if not overwrite and dense_outputs_ready(openmvs_dir):
        print("[CACHE] Existing dense output detected.")
        print("[SKIP] DensifyPointCloud")
    else:
        _invalidate_from(openmvs_dir, "dense")
        densify_code = _run_process(
            executable=openmvs_bin / "DensifyPointCloud.exe",
            args=build_densify_args(
                openmvs_dir,
                safe_mode=False,
                mask_path=mask_path,
                profile=profile,
            ),
            log_path=densify_log,
            cwd=openmvs_dir,
            raise_on_error=False,
        )

        if densify_code != 0 and not dense_outputs_ready(openmvs_dir):
            if not is_retryable_densify_exit_code(densify_code):
                raise RuntimeError(
                    "DensifyPointCloud.exe failed with exit code {}. See {}".format(
                        densify_code,
                        densify_log,
                    )
                )

            print("[WARNING] OpenMVS access violation detected.")
            print("[RETRY] Safe densify mode (conservative thread count).")

            _remove_paths((
                openmvs_dir / "scene_dense.mvs",
                openmvs_dir / "scene_dense.ply",
            ))

            safe_log = logs_dir / "openmvs_densify_safe_retry.log"

            safe_code = _run_process(
                executable=openmvs_bin / "DensifyPointCloud.exe",
                args=build_densify_args(
                    openmvs_dir,
                    safe_mode=True,
                    mask_path=mask_path,
                    profile=profile,
                ),
                log_path=safe_log,
                cwd=openmvs_dir,
                raise_on_error=False,
            )

            if safe_code != 0 and not dense_outputs_ready(openmvs_dir):
                raise RuntimeError(
                    "DensifyPointCloud safe retry failed with exit code {}. See {}".format(
                        safe_code,
                        safe_log,
                    )
                )

    _require_files(
        (
            openmvs_dir / "scene_dense.mvs",
            openmvs_dir / "scene_dense.ply",
        ),
        "DensifyPointCloud",
    )

    print("[4/6] OpenMVS mesh reconstruction...")
    if not overwrite and mesh_output_ready(openmvs_dir):
        print("[CACHE] Existing reconstructed mesh detected.")
        print("[SKIP] ReconstructMesh")
    else:
        _invalidate_from(openmvs_dir, "mesh")
        _run_process(
            executable=openmvs_bin / "ReconstructMesh.exe",
            args=build_reconstruct_mesh_args(openmvs_dir),
            log_path=logs_dir / "openmvs_reconstruct_mesh.log",
            cwd=openmvs_dir,
        )
    _require_files(
        (openmvs_dir / "scene_mesh.ply",),
        "ReconstructMesh",
    )

    print("[5/6] OpenMVS mesh refinement...")
    if not overwrite and refined_output_ready(openmvs_dir):
        print("[CACHE] Existing refined mesh detected.")
        print("[SKIP] RefineMesh")
    else:
        _invalidate_from(openmvs_dir, "refine")
        _run_process(
            executable=openmvs_bin / "RefineMesh.exe",
            args=build_refine_mesh_args(openmvs_dir, profile=profile),
            log_path=logs_dir / "openmvs_refine_mesh.log",
            cwd=openmvs_dir,
        )
    _require_files(
        (openmvs_dir / "scene_refined.ply",),
        "RefineMesh",
    )

    print("[6/6] OpenMVS mesh texturing...")
    texture_ran = False
    if not overwrite and texture_outputs_ready(openmvs_dir):
        print("[CACHE] Existing textured OBJ detected with current texture recipe.")
        print("[SKIP] TextureMesh")
    else:
        if (openmvs_dir / "object.obj").exists():
            print("[INFO] Legacy texture cache detected; rerunning TextureMesh for V0.7.3 workaround.")
        _invalidate_from(openmvs_dir, "texture")
        _run_process(
            executable=openmvs_bin / "TextureMesh.exe",
            args=build_texture_mesh_args(
                openmvs_dir,
                masked=mask_path is not None,
            ),
            log_path=logs_dir / "openmvs_texture_mesh.log",
            cwd=openmvs_dir,
        )
        texture_ran = True
    _require_files(
        (openmvs_dir / "object.obj",),
        "TextureMesh",
    )
    if texture_ran:
        _write_texture_recipe(
            openmvs_dir,
            masked=mask_path is not None,
        )

    write_mesh_recipe(openmvs_dir, profile)

    texture_outputs = _find_texture_outputs(
        openmvs_dir
    )

    return {
        "undistorted_dir": str(undistorted_dir),
        "scene": str(openmvs_dir / "scene.mvs"),
        "dense_mvs": str(openmvs_dir / "scene_dense.mvs"),
        "dense_ply": str(openmvs_dir / "scene_dense.ply"),
        "mesh_ply": str(openmvs_dir / "scene_mesh.ply"),
        "refined_ply": str(openmvs_dir / "scene_refined.ply"),
        "obj": texture_outputs["obj"],
        "mtl": texture_outputs["mtl"],
        "textures": texture_outputs["textures"],
        "mask_path": str(mask_path) if mask_path is not None else None,
        "profile": dict(profile),
        "recipe": str(_mesh_recipe_path(openmvs_dir)),
        "recipe_change_stage": recipe_change_stage,
        "logs": {
            "undistort": str(
                logs_dir / "colmap_image_undistorter.log"
            ),
            "interface": str(
                logs_dir / "openmvs_interface_colmap.log"
            ),
            "densify": str(
                logs_dir / "openmvs_densify.log"
            ),
            "reconstruct": str(
                logs_dir / "openmvs_reconstruct_mesh.log"
            ),
            "refine": str(
                logs_dir / "openmvs_refine_mesh.log"
            ),
            "texture": str(
                logs_dir / "openmvs_texture_mesh.log"
            ),
        },
    }
