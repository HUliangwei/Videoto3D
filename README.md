# Videoto3D

Videoto3D 是一个本地优先的视频 / 图像到 3D 重建工具链。**V1.1.2 在 Shared + Mesh/Splat 双 Route 核心之上提供定型版 Local Web Studio：新建 Run、视频导入、浏览器 SAM2 框选、执行两条 Route、可见进度/实时日志，以及可迁移的 GLB/PLY Web Viewer。项目继续自动管理 `env/core`、`env/seg`、`env/gui`。**

```text
Video
 └─ FFmpeg → frames/                       Shared
       ├─ SAM2 → masks/                   Shared
       └─ COLMAP RGB SfM → colmap/        Shared
              ├─ OpenMVS → OBJ → GLB      Mesh Route
              └─ Brush raw PLY            Splat Route
                       ↓
                 Splat Cleanup
                 (COLMAP cameras + SAM2 masks)
                       ↓
                 final Splat PLY
```

核心原则：

- COLMAP 始终使用完整 RGB 获得稳定相机位姿，不重新做 masked SfM。
- SAM2 Mask 是两条 Route 共享的目标识别结果。
- Mesh Route 在 OpenMVS 阶段使用 Mask。
- Splat Route 保留 V0.10 object-only sparse 作为 Brush 初始化优化，但**最终主体隔离由 Brush 之后的 Splat Cleanup 负责**。
- 不新增第二套分割模型、不维护自定义 Brush、不增加 DBSCAN/第二套 SfM。

---

## 0. V1.1 项目内环境与 GUI Control

### 外部前置（首次使用前只安装一次）

A1 策略下，Videoto3D **不内嵌/自动下载 Conda**。系统必须已有 Anaconda 或 Miniconda；GUI 前端还需要 Node.js/npm。先验证：

```powershell
conda --version
node --version
npm --version
```

如果 `conda --version` 不可用，请先安装 Anaconda/Miniconda，重新打开 PowerShell/Anaconda Prompt，再执行 `python app.py gui`。如果 Conda 缺失，V1.1 bootstrap 会输出 `[PREREQ][MISSING] Conda` 和重试指令，而不是打印 Python traceback。

Conda 是唯一外部 Python 环境前置；Videoto3D 不要求手工激活项目环境。项目会按需在根目录创建：

```text
env/
├─ core/   # 主 CLI / pipeline 调度
├─ seg/    # PyTorch CUDA + SAM2
└─ gui/    # FastAPI + Uvicorn
```

正常启动 GUI：

```powershell
python app.py gui
```

V1.1 日常流程默认直接在网页完成：

```text
New Run
  ↓ 选择本地视频并上传到 workspace/runs/<run_id>/source/
Extract (FFmpeg core job)
  ↓
Browser ROI
  ↓ Generate Masks (SAM2 core job)
Shared mask READY
  ├─ Run Mesh  → sparse → OpenMVS → GLB
  └─ Run Splat → sparse → Brush → Cleanup → PLY
        ↓
Live Job Log + Quality + Web Viewer
```

GUI Control **不会复制 pipeline 算法**。所有按钮都启动项目内 `env/core/python.exe app.py ...`，因此 CLI 与网页共用同一份 Shared / Mesh / Splat 实现。Splat Settings 暴露现有 `steps / max-splats / max-resolution / foreground-ratio / min-foreground-observations / cleanup-ratio / cleanup-min-views` 参数。

`Exit Studio` 是正常退出方式；V1.1 同时修复父/子 GUI Python 进程的 Ctrl+C 转发，Ctrl+C 会向 GUI server 请求 graceful shutdown，失败时才终止子进程。

### V1.1.1+ 可见任务进度

GUI job 不再只显示终端日志。任务运行时，Run 页面会显示 sticky Progress Card，顶部导航也会持续显示当前任务摘要：

```text
SAM2 masks      76 / 120 masks      63.3%
Brush training  10000 / 30000 steps 33.3%
Mesh Route      Reconstructing mesh Step 3 / 6
```

进度遵循“有可靠计数才显示百分比”的规则：

- SAM2：直接统计 `masks/*.png` 与 `frames/*.jpg`，显示真实 `mask_count / frame_count`。
- Brush：优先解析训练输出；同时使用 `splat/exports/<run_id>_<iter>.ply` 的最新 iteration 作为可靠 checkpoint 进度，因此至少每次 Brush export 会更新一次。
- Extract：显示当前已写入 frames 数量；无法预知最终帧数时不伪造百分比。
- Mesh/OpenMVS：显示 Shared → Dense → Reconstruct → Refine → Texture → GLB 阶段 Stepper，不伪造工具内部百分比。
- Live Log 默认折叠；任务失败时自动展开，`Cancel Job` 仍可随时使用。

SAM2 运行时 ROI 会锁定，`Generate Masks` 立即变为 `Generating Masks…`，避免用户误以为点击没有生效。

首次运行会自动创建 `env/core`，随后按需创建 `env/gui`；第一次运行 SAM2 Mask 时才创建 `env/seg`。环境 recipe 未变化时会直接复用，不重复安装。

环境状态与修复：

```powershell
python app.py env status
python app.py env repair <core|seg|gui>

# 也可以指定具体环境：
python app.py env repair core
python app.py env repair gui
python app.py env repair seg
```

`env/` 是本机生成目录，不进入 Git。SAM2 源码/checkpoint 仍属于 `runtime/sam2/`，Run 数据仍属于 `workspace/`。

GUI 保持模块边界：`gui/control` 是 Videoto3D 强耦合控制层，`gui/viewer` 只负责通用 GLB / Gaussian Splat 展示，可独立迁移到其他项目。

V1.1.2 增加只读 **Paths & Runtime** inspector，可查看并复制：项目 Root/Workspace/Runtime、`env/core|seg|gui` Python、FFmpeg/COLMAP/OpenMVS/Brush/Blender 已解析路径，以及当前 Run 的 frames/masks/colmap/mesh/splat/GLB/PLY 路径。本版不在网页内修改工具路径，避免把查看与配置写入混在一起。

`env/core` recipe 现已固定包含 Pillow，并在环境健康检查中验证 `PIL`，避免 Mesh Route mask validation 因缺 Pillow 中断。

**Conda CLI 兼容性：** V1.0.1 Hotfix 1 不再给 `conda env create/update` 传入 `-y`，以兼容用户现有 Anaconda/Miniconda 的 `conda-env` CLI；无需升级 Conda。

### Web Viewer 方向控制

V1.0.2 起将固定 `camera.up` 的 OrbitControls 改为可自由滚转的 TrackballControls。左键可以跨极点/滚转相机；另提供 `Roll Left / Flip / Roll Right`，用于输入资产自身朝向不是 Y-up 或像 Teddy 一样倒置时快速转正。`Front/Back/Left/Right/Top/Bottom/Iso`、Fit、Auto Rotate 与 Fullscreen 继续保留。

## 1. Run 文件架构

```text
workspace/runs/<run_id>/
├─ run.json
├─ source/
├─ frames/                       # Shared: 原始 RGB
├─ masks/                        # Shared: SAM2
├─ segmentation/                 # Shared: Mask report / QA
├─ colmap/                       # Shared: 完整 RGB SfM
├─ mesh/                         # Mesh Route 私有中间产物
│  ├─ mvs_colmap/
│  ├─ openmvs_masks/
│  ├─ openmvs/
│  └─ blender/
├─ splat/                        # Splat Route 私有中间产物
│  ├─ dataset/                   # Brush staging
│  │  ├─ images/
│  │  ├─ masks/
│  │  └─ sparse/0/              # object-only points3D init
│  ├─ object_sparse_report.json
│  ├─ recipe.json
│  ├─ exports/                   # Brush checkpoints
│  ├─ raw/
│  │  └─ <run_id>_raw.ply       # Brush 原始最终 PLY，Cleanup 永不覆盖它
│  └─ cleanup_report.json
├─ output/
│  ├─ <run_id>.glb
│  └─ <run_id>_splat.ply        # Cleanup 后最终 Splat
├─ quality/
│  ├─ report.json               # 给程序 / Web GUI
│  └─ report.md                 # 给人阅读
└─ logs/
   ├─ shared/
   ├─ mesh/
   └─ splat/
```

磁盘目录保持扁平；`shared` 与 `routes` 仅在 `run.json` 中表达逻辑状态。

---

## 2. 一键 Route 命令

### Mesh Route

```text
python app.py route mesh --run <run_id> [--input <video>] [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1] [--output-name name.glb] [--output <path>]
```

新 Run：

```powershell
python app.py route mesh --run cup_001 --input "D:\Videos\cup.mp4"
```

自动执行：

```text
extract → mask → sparse → OpenMVS Dense/Reconstruct/Refine/Texture → GLB
```

已有 Run 自动跳过 ready 阶段：

```powershell
python app.py route mesh --run teddy_001
```

### Mesh Route 参数（V1.1.2）

网页 `Mesh Settings` 与 CLI 使用同一组安全参数：

```text
Undistort max image size   2000
Dense resolution level        0
Dense number views             0   # 0 = OpenMVS default / Auto
Dense max threads              0   # 0 = OpenMVS default / Auto
Refine resolution level        1
```

参数变化采用 recipe-aware rerun：Undistort 参数变化从 COLMAP undistort / Interface 开始重跑；Dense 参数变化只从 Dense 往后；Refine 参数变化只从 Refine 往后。Shared frames / SAM2 / 原始 RGB COLMAP sparse 不受影响。

TextureMesh 的 OpenMVS 2.4.0 workaround 仍锁定为：

```text
--ignore-mask-label 0
--global-seam-leveling 0
--local-seam-leveling 0
```

网页只展示这一 workaround，不允许误开启 seam leveling。

### Splat Route

```text
python app.py route splat --run <run_id> [--input <video>] [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]
```

新 Run：

```powershell
python app.py route splat --run cup_001 --input "D:\Videos\cup.mp4"
```

自动执行：

```text
extract → mask → sparse
→ object-only sparse staging（训练优化）
→ Brush training → splat/raw/<run_id>_raw.ply
→ final Gaussian multi-view Cleanup
→ output/<run_id>_splat.ply
```

轻量验证：

```powershell
python app.py route splat --run teddy_001 --steps 10000 --max-splats 1000000 --max-resolution 960
```

仅调整 Cleanup 时，例如：

```powershell
python app.py route splat --run teddy_001 --cleanup-ratio 0.75 --cleanup-min-views 4
```

如果 Brush training recipe 不变且 raw PLY 已存在，程序会：

```text
[SKIP] splat.train
[RUN ] splat.cleanup
```

因此调主体清理参数不需要重新跑 30k Brush。

---

## 3. 细粒度 run 命令

```text
python app.py doctor
```

```text
python app.py run extract --run <run_id> --input <video>
```

```text
python app.py run mask --run <run_id> [--box x0,y0,x1,y1]
```

```text
python app.py run sparse --run <run_id>
```

```text
python app.py run mesh --run <run_id> [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1]
```

```text
python app.py run glb --run <run_id> [--output-name name.glb] [--output <path>]
```

```text
python app.py run splat --run <run_id> [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]
```

`run splat` 会依次完成 Brush raw training + Cleanup。工程调试时可使用 `route splat` 的缓存逻辑只重跑必要部分。

---

## 4. 查看命令

```text
python app.py view masks --run <run_id>
```

```text
python app.py view sparse --run <run_id>
```

```text
python app.py view splat-init --run <run_id>
```

`splat-init` 用于查看 `splat/dataset/sparse/0`：相机位姿与完整 RGB SfM 相同，只过滤 Brush 初始化用的背景 points3D。报告位于：

```text
workspace/runs/<run_id>/splat/object_sparse_report.json
```

```text
python app.py view mesh (--run <run_id> | --path <obj>)
```

```text
python app.py view glb (--run <run_id> | --path <glb>)
```

```text
python app.py view splat (--run <run_id> | --path <ply>)
```

所有 COLMAP / Blender / Brush Viewer 都使用 detached process；关闭 Viewer 后不需要再按 `Ctrl+C`。

Blender 手动导入 GLB 后如果模型呈灰白色，请切换 **Material Preview**；GLB 内嵌纹理没有因此丢失。详见 `docs/troubleshooting/blender-glb-viewing.md`。

---

## 5. Run 进度：Shared + 双 Route

```text
python app.py runs list
```

示例：

```text
RUN ID              SHARED          MESH ROUTE       SPLAT ROUTE
------------------------------------------------------------------------
teddy_001           READY           COMPLETE         COMPLETE
cup_001             READY           COMPLETE         PENDING
shoe_001            MASK PENDING    BLOCKED          BLOCKED
```

```text
python app.py runs show <run_id>
```

V0.11 一级进度刻意保持简洁：

```text
Shared
  extract     : ready
  mask        : ready
  sparse      : ready

Mesh Route
  reconstruct : ready
  glb         : ready

Splat Route
  train       : ready
  cleanup     : ready
  ply         : ready
```

详细数字进入 Quality Report，而不是把所有内部 OpenMVS/Brush 子阶段堆在一级状态页。

---

## 6. Splat Cleanup：最终 Gaussian 主体清理

V0.10 已证明只过滤 Brush 初始化 points3D 能减少背景，但 Brush 训练过程仍可能 densify / move / clone 出新的外围 Gaussian。因此 V0.11 在 **Brush 最终 raw PLY 之后**做一次结果级清理。

```text
Brush raw Gaussian center (X,Y,Z)
        ↓
原始 COLMAP registered cameras
        ↓
投影到每个有效 frame
        ↓
查询同一帧 SAM2 mask
        ↓
foreground votes / valid views
        ↓
默认：support ratio >= 0.70
      valid views >= 3
        ↓
KEEP / REMOVE Gaussian record
```

这一步：

- 不重新训练 Brush。
- 不修改 Gaussian 的 SH、opacity、scale、rotation 等属性，只删除不满足主体支持的完整 Gaussian records。
- 使用已经共享的 `colmap/` 和 `masks/`，不增加新的识别环节。
- 原始 Brush PLY 永远保留在 `splat/raw/`，最终清理结果写入 `output/`。

清理报告：

```text
workspace/runs/<run_id>/splat/cleanup_report.json
```

典型指标：raw splats、clean splats、removed splats、removal ratio、mean valid views、foreground support。

---

## 7. Object-only Sparse 仍保留，但只是训练优化

V0.10 的 object sparse staging 继续存在：

```text
完整 RGB COLMAP cameras/images 保留
points3D 根据 SAM2 多视角投票过滤
→ Brush initialization
```

默认：

```text
foreground ratio >= 0.60
foreground observations >= 2
```

这可以降低 Brush 初始背景负担，但**最终隔离标准是 V0.11 Cleanup，而不是 object sparse**。

---

## 8. Quality Report

```text
python app.py quality --run <run_id>
```

生成：

```text
workspace/runs/<run_id>/quality/report.json
workspace/runs/<run_id>/quality/report.md
```

报告汇总：

```text
Shared
  Frames / Masks
  COLMAP registration rate
  Sparse points
  Reprojection error

Mesh Route
  Dense points
  Final vertices / faces
  GLB path / size

Splat Route
  Training steps
  Raw splats
  Clean splats
  Removed splats / removal ratio
  Cleanup threshold
  Final PLY path / size
```

`report.json` 是未来本地 Web GUI 的数据接口；`report.md` 供人快速审查。

---

## 9. V0.10 → V0.11 非破坏性迁移

第一次读取 V0.10 `run.json` 时自动升级 schema。

如果 V0.10 已有：

```text
output/teddy_001_splat.ply
```

V0.11 会复制保存为：

```text
splat/raw/teddy_001_raw.ply
```

然后状态变为：

```text
train   READY
cleanup PENDING
ply     PENDING
```

因此**不需要重新跑 Brush**，直接：

```powershell
python app.py route splat --run teddy_001
```

程序会复用 raw PLY，只运行 Cleanup。

---

## 10. OpenMVS 2.4.0 TextureMesh workaround

Mesh Route 将 SAM2：

```text
frame_0001.jpg.png
```

staging 成 OpenMVS：

```text
frame_0001.mask.png
```

并继续保留已验证 workaround：

```text
--ignore-mask-label 0
--global-seam-leveling 0
--local-seam-leveling 0
```

RCA：`docs/bugs/BUG-0001-openmvs-2.4.0-texture-black-artifacts.md`。

---

## 11. 工程记录规范

- Bug / Incident / RCA：`docs/bugs/`
- 架构决策 ADR：`docs/architecture/`
- 用户排障：`docs/troubleshooting/`
- 设计 / 实施计划：`docs/superpowers/specs/`、`docs/superpowers/plans/`

V0.11 架构决策：`docs/architecture/ADR-0004-post-brush-splat-cleanup.md`。

`README.md` 是 CLI 权威手册；命令、参数、Run 状态、文件架构或 workaround 改变时必须同步更新，并由测试校验 canonical commands。

当前版本：**Videoto3D V1.1.2 Finalized Local Studio Foundation**。

---

## GitHub 发布

项目已忽略本机生成/大体积目录：`env/`、`runtime/`、`workspace/`、`config/tools.json`、前端 `node_modules/dist`。上传前建议先执行：

```powershell
git status
git add .
git status
git commit -m "release: finalize Videoto3D v1.1.2 studio"
git push
```

首次建立远程仓库时，在 GitHub 新建空仓库后执行：

```powershell
git init
git branch -M main
git add .
git commit -m "release: Videoto3D v1.1.2"
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/Videoto3D.git
git push -u origin main
```

如果本地已经存在 Git 历史/remote，不要再次 `git init` 或重复 `git remote add origin`。
