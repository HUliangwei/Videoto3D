"""Canonical, data-driven CLI registry for Videoto3D V1.1.2."""

COMMAND_SPECS = {
    "env.status": {
        "tokens": ("env", "status"),
        "command": "python app.py env status",
        "description": "查看项目内 core / seg / gui Conda 环境状态。",
        "input": "env/ + config/envs/*.yml",
        "output": "READY / MISSING / STALE / BROKEN 状态表",
        "next": "正常情况下无需手动处理；异常时使用 env repair",
        "tools": (),
    },
    "env.repair": {
        "tokens": ("env", "repair"),
        "command": "python app.py env repair <core|seg|gui>",
        "description": "只重建指定的项目内 Conda 环境，不触碰 runtime、workspace 或其他环境。",
        "input": "config/envs/<environment>.yml",
        "output": "env/<environment>",
        "next": "重新执行原 Videoto3D 命令",
        "tools": (),
    },
    "gui": {
        "tokens": ("gui",),
        "command": "python app.py gui",
        "description": "启动 Videoto3D V1.1.2 本地控制 Studio：New Run、浏览器 SAM2 ROI、Mesh/Splat Route、参数/路径查看、可见进度与 3D 结果查看。",
        "input": "workspace/runs + 项目内 core/seg/gui 环境 + 本机工具链",
        "output": "http://127.0.0.1:8765 本地控制网页；所有重建仍调用现有 core CLI",
        "next": "在浏览器中新建/选择 Run，并执行 Shared、Mesh Route 或 Splat Route",
        "tools": (),
    },
    "doctor": {
        "tokens": ("doctor",),
        "command": "python app.py doctor",
        "description": "检查 Videoto3D 全部外部工具与本机运行环境是否可用。",
        "input": "config/tools.json、runtime/ 以及本机已安装工具",
        "output": "环境检查结果；不会执行重建任务",
        "next": "python app.py route mesh --run teddy_001 --input <video>",
        "tools": ("colmap", "brush", "blender", "ffmpeg", "openmvs"),
    },
    "route.mesh": {
        "tokens": ("route", "mesh"),
        "command": "python app.py route mesh --run <run_id> [--input <video>] [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1] [--output-name name.glb] [--output <path>]",
        "description": "一键执行 Shared 阶段 + Mesh Route：extract → mask → sparse → OpenMVS → GLB；已完成阶段自动跳过。",
        "input": "已有 Run；新 Run 必须通过 --input 指定视频",
        "output": "workspace/runs/<run_id>/output/<run_id>.glb",
        "next": "python app.py view glb --run <run_id>",
        "tools": (),
    },
    "route.splat": {
        "tokens": ("route", "splat"),
        "command": "python app.py route splat --run <run_id> [--input <video>] [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]",
        "description": "一键执行 Shared 阶段 + Splat Route：Brush raw PLY → SAM2/COLMAP 多视角 Cleanup → 最终主体 Gaussian Splat PLY；已完成训练可只重跑 Cleanup。",
        "input": "已有 Run；新 Run 必须通过 --input 指定视频",
        "output": "workspace/runs/<run_id>/output/<run_id>_splat.ply",
        "next": "python app.py view splat --run <run_id>",
        "tools": (),
    },
    "run.extract": {
        "tokens": ("run", "extract"),
        "command": "python app.py run extract --run <run_id> --input <video>",
        "description": "创建/更新一个 Run，并使用 FFmpeg 从输入视频抽取原始 RGB 帧。源视频会复制进该 Run 的 source/。",
        "input": "--input 指定的视频文件",
        "output": "workspace/runs/<run_id>/source + frames",
        "next": "python app.py run mask --run <run_id>",
        "tools": ("ffmpeg",),
    },
    "run.mask": {
        "tokens": ("run", "mask"),
        "command": "python app.py run mask --run <run_id> [--box x0,y0,x1,y1]",
        "description": "使用首帧目标框执行 SAM2 Mask 传播；CLI 未提供 --box 时打开交互框选，GUI 直接传入浏览器 ROI。",
        "input": "workspace/runs/<run_id>/frames",
        "output": "workspace/runs/<run_id>/masks + segmentation/report.json",
        "next": "python app.py view masks --run <run_id>",
        "tools": (),
    },
    "run.sparse": {
        "tokens": ("run", "sparse"),
        "command": "python app.py run sparse --run <run_id>",
        "description": "使用该 Run 的原始 RGB 图像执行 COLMAP SfM，估计稳定相机位姿与稀疏点云。",
        "input": "workspace/runs/<run_id>/frames",
        "output": "workspace/runs/<run_id>/colmap",
        "next": "python app.py view sparse --run <run_id>",
        "tools": ("colmap",),
    },
    "run.mesh": {
        "tokens": ("run", "mesh"),
        "command": "python app.py run mesh --run <run_id> [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1]",
        "description": "使用共享 COLMAP 相机位姿 + SAM2 Mask 执行 Mesh Route 的 OpenMVS Dense / Reconstruct / Refine / Texture。",
        "input": "共享 colmap + frames + masks",
        "output": "workspace/runs/<run_id>/mesh/openmvs/object.obj 及纹理",
        "next": "python app.py run glb --run <run_id>",
        "tools": ("colmap", "openmvs"),
    },
    "run.glb": {
        "tokens": ("run", "glb"),
        "command": "python app.py run glb --run <run_id> [--output-name name.glb] [--output <path>]",
        "description": "使用 Blender 将 Mesh Route OBJ/纹理导出为自包含 GLB。",
        "input": "workspace/runs/<run_id>/mesh/openmvs/object.obj",
        "output": "workspace/runs/<run_id>/output/<name>.glb；可选 --output 导出副本",
        "next": "python app.py view glb --run <run_id>",
        "tools": ("blender",),
    },
    "run.splat": {
        "tokens": ("run", "splat"),
        "command": "python app.py run splat --run <run_id> [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]",
        "description": "训练 Brush raw Gaussian Splat，然后复用共享 COLMAP cameras + SAM2 masks 对最终 Gaussian 做多视角主体 Cleanup。",
        "input": "共享 frames + masks + colmap/sparse/0",
        "output": "workspace/runs/<run_id>/splat + output/<run_id>_splat.ply",
        "next": "python app.py view splat --run <run_id>",
        "tools": ("brush",),
    },
    "view.masks": {
        "tokens": ("view", "masks"),
        "command": "python app.py view masks --run <run_id>",
        "description": "检查指定 Run 的 SAM2 分割质量，展示原图 + Mask 叠加图。",
        "input": "workspace/runs/<run_id>/frames + masks",
        "output": "workspace/runs/<run_id>/segmentation/mask_qa.jpg",
        "next": "python app.py run sparse --run <run_id>",
        "tools": (),
    },
    "view.sparse": {
        "tokens": ("view", "sparse"),
        "command": "python app.py view sparse --run <run_id>",
        "description": "在 COLMAP GUI 中查看共享的原始 RGB 稀疏重建。",
        "input": "workspace/runs/<run_id>/colmap/sparse/0",
        "output": "启动独立 COLMAP GUI",
        "next": "选择 Mesh Route 或 Splat Route",
        "tools": ("colmap",),
    },
    "view.splat-init": {
        "tokens": ("view", "splat-init"),
        "command": "python app.py view splat-init --run <run_id>",
        "description": "在 COLMAP GUI 中查看 Splat Route 的 object-only sparse 初始化：保留全部相机，只过滤背景 points3D。",
        "input": "workspace/runs/<run_id>/splat/dataset/sparse/0",
        "output": "启动独立 COLMAP GUI",
        "next": "python app.py run splat --run <run_id>",
        "tools": ("colmap",),
    },
    "view.mesh": {
        "tokens": ("view", "mesh"),
        "command": "python app.py view mesh (--run <run_id> | --path <obj>)",
        "description": "在 Blender 中查看 Mesh Route OBJ，或通过 --path 查看任意 OBJ。",
        "input": "Run 的 mesh/openmvs/object.obj 或 --path",
        "output": "启动独立 Blender Viewer",
        "next": "python app.py run glb --run <run_id>",
        "tools": ("blender",),
    },
    "view.glb": {
        "tokens": ("view", "glb"),
        "command": "python app.py view glb (--run <run_id> | --path <glb>)",
        "description": "在 Blender Material Preview 查看最终 GLB，或通过 --path 查看任意 GLB。",
        "input": "Mesh Route manifest 记录的 GLB 或 --path",
        "output": "启动独立 Blender Viewer",
        "next": "Mesh Route 完成",
        "tools": ("blender",),
    },
    "view.splat": {
        "tokens": ("view", "splat"),
        "command": "python app.py view splat (--run <run_id> | --path <ply>)",
        "description": "使用 Brush Viewer 查看 Gaussian Splat PLY，或通过 --path 查看任意 Splat PLY。",
        "input": "Splat Route manifest 记录的 PLY 或 --path",
        "output": "启动独立 Brush Viewer",
        "next": "Splat Route 完成",
        "tools": ("brush",),
    },
    "quality": {
        "tokens": ("quality",),
        "command": "python app.py quality --run <run_id>",
        "description": "生成并打印指定 Run 的统一质量报告，汇总 Shared、Mesh Route 与 Splat Route 指标。",
        "input": "workspace/runs/<run_id>/run.json + 已有中间/最终产物",
        "output": "workspace/runs/<run_id>/quality/report.json + report.md",
        "next": "根据报告决定是否调整 Route 参数或完成该 Run",
        "tools": (),
    },
    "runs.list": {
        "tokens": ("runs", "list"),
        "command": "python app.py runs list",
        "description": "列出所有 Run，并区分 Shared、Mesh Route、Splat Route 进度。",
        "input": "workspace/runs/*/run.json",
        "output": "终端双路线状态表",
        "next": "python app.py runs show <run_id>",
        "tools": (),
    },
    "runs.show": {
        "tokens": ("runs", "show"),
        "command": "python app.py runs show <run_id>",
        "description": "展开单个 Run 的 Shared / Mesh Route / Splat Route 子阶段状态和关键指标。",
        "input": "workspace/runs/<run_id>/run.json + route cache files",
        "output": "终端 Run 详情",
        "next": "根据未完成 Route 继续对应命令",
        "tools": (),
    },
}

LEGACY_REPLACEMENTS = {
    "extract": "python app.py run extract --run <run_id> --input <video>",
    "mask": "python app.py run mask --run <run_id>",
    "sparse": "python app.py run sparse --run <run_id>",
    "mesh": "python app.py run mesh --run <run_id>",
    "glb": "python app.py run glb --run <run_id>",
    "view": "python app.py view sparse --run <run_id>",
    "view-masks": "python app.py view masks --run <run_id>",
    "view-mesh": "python app.py view mesh --run <run_id>",
    "view-glb": "python app.py view glb --run <run_id>",
}

_TOKEN_TO_KEY = {tuple(spec["tokens"]): key for key, spec in COMMAND_SPECS.items()}
_VALUE_OPTIONS = {
    "--run": "run", "--input": "input", "--path": "path",
    "--output-name": "output_name", "--output": "output",
    "--steps": "steps", "--max-splats": "max_splats", "--max-resolution": "max_resolution",
    "--foreground-ratio": "foreground_ratio",
    "--min-foreground-observations": "min_foreground_observations",
    "--cleanup-ratio": "cleanup_ratio",
    "--cleanup-min-views": "cleanup_min_views",
    "--undistort-max-image-size": "undistort_max_image_size",
    "--dense-resolution-level": "dense_resolution_level",
    "--dense-number-views": "dense_number_views",
    "--dense-max-threads": "dense_max_threads",
    "--refine-resolution-level": "refine_resolution_level",
    "--box": "box",
}


def command_spec(key): return COMMAND_SPECS[key]
def canonical_command_lines(): return [spec["command"] for spec in COMMAND_SPECS.values()]
def _error(message): return {"kind": "error", "key": None, "message": message}


def _parse_options(args):
    options = {}; i = 0
    while i < len(args):
        token = args[i]
        if token == "--masked":
            return None, "V0.10 正式流程不使用 --masked；Mesh/Splat Route 各自在正确阶段应用 SAM2 Mask。"
        key = _VALUE_OPTIONS.get(token.lower())
        if key is None: return None, "未知参数：{}".format(token)
        if i + 1 >= len(args) or args[i + 1].startswith("--"): return None, "参数 {} 缺少值。".format(token)
        if key in options: return None, "参数 {} 重复。".format(token)
        options[key] = args[i + 1]; i += 2
    return options, None


def parse_cli_args(args):
    args = [str(x) for x in args]
    if not args or [a.lower() for a in args] in (["-h"], ["--help"], ["help"]):
        return {"kind": "help", "key": None, "options": {}}
    if len(args) == 1 and args[0].lower() in LEGACY_REPLACEMENTS:
        legacy = args[0].lower()
        return {"kind": "legacy", "key": None, "legacy": legacy, "replacement": LEGACY_REPLACEMENTS[legacy], "options": {}}
    lowered = [a.lower() for a in args]
    if lowered[:2] == ["runs", "list"]:
        return {"kind": "command", "key": "runs.list", "options": {}} if len(args) == 2 else _error("runs list 不接受额外参数。")
    if lowered[:2] == ["runs", "show"]:
        return {"kind": "command", "key": "runs.show", "options": {"run": args[2]}} if len(args) == 3 else _error("用法：python app.py runs show <run_id>")
    if lowered[:2] == ["env", "status"]:
        return {"kind": "command", "key": "env.status", "options": {}} if len(args) == 2 else _error("env status 不接受额外参数。")
    if lowered[:2] == ["env", "repair"]:
        if len(args) != 3:
            return _error("用法：python app.py env repair <core|seg|gui>")
        environment = lowered[2]
        if environment not in ("core", "seg", "gui"):
            return _error("env repair 仅支持 core / seg / gui。")
        return {"kind": "command", "key": "env.repair", "options": {"environment": environment}}
    if lowered[0] == "doctor":
        return {"kind": "command", "key": "doctor", "options": {}} if len(args) == 1 else _error("doctor 不接受额外参数。")
    if lowered[0] == "gui":
        return {"kind": "command", "key": "gui", "options": {}} if len(args) == 1 else _error("gui 不接受额外参数。")
    if lowered[0] == "quality":
        options, error = _parse_options(args[1:])
        if error: return _error(error)
        if not options.get("run"): return _error("quality 必须指定 --run <run_id>。")
        if set(options) != {"run"}: return _error("quality 仅接受 --run <run_id>。")
        return {"kind": "command", "key": "quality", "options": options}
    if len(args) < 2: return _error("未知命令：{}".format(" ".join(args)))
    key = _TOKEN_TO_KEY.get(tuple(lowered[:2]))
    if key is None: return _error("未知命令：{}".format(" ".join(args)))
    options, error = _parse_options(args[2:])
    if error: return _error(error)

    run_id = options.get("run"); path = options.get("path")
    if key == "run.extract":
        if not run_id: return _error("run extract 必须指定 --run <run_id>。")
        if not options.get("input"): return _error("run extract 必须指定 --input <video>。")
    elif key.startswith("run.") or key.startswith("route.") or key == "view.splat-init":
        if not run_id: return _error("{} 必须指定 --run <run_id>。".format(" ".join(lowered[:2])))
    elif key in ("view.masks", "view.sparse"):
        if not run_id: return _error("{} 必须指定 --run <run_id>。".format(" ".join(lowered[:2])))
        if path: return _error("{} 不支持 --path。".format(" ".join(lowered[:2])))
    elif key in ("view.mesh", "view.glb", "view.splat"):
        if bool(run_id) == bool(path): return _error("{} 必须且只能指定 --run 或 --path 其中一个。".format(" ".join(lowered[:2])))

    if options.get("input") and key not in ("run.extract", "route.mesh", "route.splat"):
        return _error("--input 仅用于 run extract / route mesh / route splat。")
    if path and key not in ("view.mesh", "view.glb", "view.splat"):
        return _error("--path 仅用于 view mesh / view glb / view splat。")
    if options.get("box") is not None:
        if key != "run.mask":
            return _error("--box 仅用于 run mask。")
        parts = str(options["box"]).split(",")
        if len(parts) != 4:
            return _error("--box 格式必须为 x0,y0,x1,y1。")
        try:
            box = tuple(int(part.strip()) for part in parts)
        except ValueError:
            return _error("--box 必须包含 4 个整数。")
        x0, y0, x1, y1 = box
        if min(box) < 0 or x1 <= x0 or y1 <= y0:
            return _error("--box 必须满足 0<=x0<x1 且 0<=y0<y1。")
        options["box"] = box

    profile_keys = ("steps", "max_splats", "max_resolution")
    if any(options.get(n) is not None for n in profile_keys) and key not in ("run.splat", "route.splat"):
        return _error("--steps / --max-splats / --max-resolution 仅用于 Splat Route。")
    for name in profile_keys:
        if options.get(name) is not None:
            try: value = int(options[name])
            except ValueError: return _error("--{} 必须是正整数。".format(name.replace("_", "-")))
            if value <= 0: return _error("--{} 必须是正整数。".format(name.replace("_", "-")))

    filter_keys = ("foreground_ratio", "min_foreground_observations")
    if any(options.get(n) is not None for n in filter_keys) and key not in ("run.splat", "route.splat"):
        return _error("Object-only sparse 参数仅用于 Splat Route。")
    if options.get("foreground_ratio") is not None:
        try: ratio = float(options["foreground_ratio"])
        except ValueError: return _error("--foreground-ratio 必须是 (0,1] 内数字。")
        if not (0.0 < ratio <= 1.0): return _error("--foreground-ratio 必须是 (0,1] 内数字。")
    if options.get("min_foreground_observations") is not None:
        try: obs = int(options["min_foreground_observations"])
        except ValueError: return _error("--min-foreground-observations 必须是正整数。")
        if obs <= 0: return _error("--min-foreground-observations 必须是正整数。")

    cleanup_keys = ("cleanup_ratio", "cleanup_min_views")
    if any(options.get(n) is not None for n in cleanup_keys) and key not in ("run.splat", "route.splat"):
        return _error("--cleanup-ratio / --cleanup-min-views 仅用于 Splat Route。")
    if options.get("cleanup_ratio") is not None:
        try: cleanup_ratio = float(options["cleanup_ratio"])
        except ValueError: return _error("--cleanup-ratio 必须是 (0,1] 内数字。")
        if not (0.0 < cleanup_ratio <= 1.0): return _error("--cleanup-ratio 必须是 (0,1] 内数字。")
    if options.get("cleanup_min_views") is not None:
        try: cleanup_views = int(options["cleanup_min_views"])
        except ValueError: return _error("--cleanup-min-views 必须是正整数。")
        if cleanup_views <= 0: return _error("--cleanup-min-views 必须是正整数。")

    mesh_profile_keys = (
        "undistort_max_image_size",
        "dense_resolution_level",
        "dense_number_views",
        "dense_max_threads",
        "refine_resolution_level",
    )
    if any(options.get(n) is not None for n in mesh_profile_keys) and key not in ("run.mesh", "route.mesh"):
        return _error("OpenMVS Mesh 参数仅用于 run mesh / route mesh。")
    for name in mesh_profile_keys:
        if options.get(name) is None:
            continue
        try:
            value = int(options[name])
        except ValueError:
            return _error("--{} 必须是整数。".format(name.replace("_", "-")))
        if name == "undistort_max_image_size" and value <= 0:
            return _error("--undistort-max-image-size 必须是正整数。")
        if name != "undistort_max_image_size" and value < 0:
            return _error("--{} 必须是非负整数；0 表示默认/Auto。".format(name.replace("_", "-")))

    if (options.get("output_name") or options.get("output")) and key not in ("run.glb", "route.mesh"):
        return _error("--output-name / --output 仅用于 GLB / Mesh Route。")
    if key in ("run.glb", "route.mesh") and options.get("output_name") and options.get("output"):
        return _error("--output-name 与 --output 只能选一个。")
    return {"kind": "command", "key": key, "options": options}


def _subst(text, options):
    if options and options.get("run"): text = text.replace("<run_id>", options["run"])
    return text


def print_command_annotation(spec, options=None):
    print("=" * 68); print("Videoto3D 命令说明"); print("=" * 68)
    print("命令：{}".format(_subst(spec["command"], options)))
    print("说明：{}".format(spec["description"])); print("输入：{}".format(_subst(spec["input"], options)))
    print("输出：{}".format(_subst(spec["output"], options))); print("下一步：{}".format(_subst(spec["next"], options)))
    print("=" * 68)


def print_cli_help():
    print("Videoto3D V1.1.2 规范命令：\n")
    for spec in COMMAND_SPECS.values():
        print("  {:<150} # {}".format(spec["command"], spec["description"]))
    print("\n完整说明请阅读项目根目录 README.md")
