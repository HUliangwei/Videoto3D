# Videoto3D

**Videoto3D V1.4** 是一个 local-first 的视频到 3D 重建 Studio。

V1.4 按真实视频采集方式维护两条并列工作流，并继续统一使用 `workspace/runs/<run_id>/` 管理输入、中间结果、日志和输出。

| Capture Method | 真实拍摄 | 定位 | 主线 |
|---|---|---|---|
| **Orbit Camera** | 目标静止，相机围绕目标运动 | **Stable** | Full-RGB COLMAP incremental SfM → OpenMVS / Brush |
| **Turntable** | 相机静止，刚体目标单轴旋转 | **Research** | Turntable-specific pose / global orbit research；V1.3 baseline 被隔离保留 |

> Canonical CLI entry：`python Videoto3D.py ...`
>
> `app.py` 仅作为内部 CLI implementation / 兼容模块，不再作为用户命令入口。

---

## V1.4 Architecture

```text
                         New Run
                            │
                  Video + Capture Method
                            │
               ┌────────────┴────────────┐
               │                         │
         Orbit Camera                Turntable
         STABLE WORKFLOW          RESEARCH WORKFLOW
               │                         │
        Object fixed               Camera fixed
        Camera moves               Object rotates
               │                         │
         Full RGB SfM             Object observations
               │                         │
          COLMAP                 Turntable pose research
      incremental mapper       structured E / global orbit
               │                         │
         Stable Sparse          research pose / geometry
               │                         │
         ┌─────┴─────┐              ┌────┴────┐
         │           │              │         │
       OpenMVS      Brush         Geometry   Gaussian
         │           │              │         │
        GLB         PLY             GLB       PLY
```

### Orbit Camera · Stable

Orbit Camera 保持已经验证的经典工程链：

```text
Video
→ FFmpeg Frames
→ Full RGB COLMAP Feature Extraction
→ Matching
→ Incremental SfM / Bundle Adjustment
→ Sparse Geometry
→ OpenMVS → Blender → GLB
→ Brush → Cleanup → PLY
```

**SAM2 Mask 不参与 Orbit Camera 的相机位姿恢复。** 背景纹理仍可帮助 COLMAP 定位；Mask 只作为后续 Mesh / Splat 的目标约束。

V1.4 以 V1.2.0 的 Orbit reconstruction behavior 为稳定基线。V1.3.x 的 Turntable 实验没有改动 `pipeline/colmap.py`，因此 V1.4 的重点是通过 workflow router 显式冻结和隔离这条稳定行为，而不是把整个工程回滚到 V1.2.0。

### Turntable · Research

Turntable 的物理条件是：

```text
Camera: fixed
Object: rigid
Motion: one dominant rotation axis
```

V1.4 将它从文件结构、运行路由和 Web 页面上与 Orbit Camera 分开。

Phase 1 把 V1.3 的 constrained-pose / adaptive-angle 实现冻结到：

```text
pipeline/workflows/turntable/legacy_v13/
```

作为研究 baseline。

后续研究主线：

```text
object observations
→ turntable-constrained relative geometry
→ shared rotation axis
→ per-frame angle hypotheses
→ cycle consistency
→ global orbit refinement
→ pose quality / observability
```

未来 SfM-free Gaussian reconstruction 也只进入 Turntable workflow，不修改稳定 Orbit Camera 工作流。

Dynamic / 4D 人体动作等非刚体重建不在当前 Turntable 范围内。

---

## Project Structure

```text
Videoto3D/
├─ Videoto3D.py
├─ app.py
├─ bootstrap.py
├─ pipeline/
│  ├─ workflows/
│  │  ├─ registry.py
│  │  ├─ orbit_camera/
│  │  │  └─ workflow.py
│  │  └─ turntable/
│  │     ├─ workflow.py
│  │     └─ legacy_v13/
│  │        ├─ reconstruction.py
│  │        └─ angle.py
│  ├─ colmap.py
│  ├─ segmentation.py
│  ├─ openmvs.py
│  ├─ brush.py
│  ├─ blender.py
│  └─ run_workspace.py
├─ gui/control/web/src/
│  ├─ pages/
│  │  ├─ RunsPage.tsx
│  │  └─ RunDetailPage.tsx
│  └─ workflows/
│     ├─ orbit-camera/OrbitCameraRunView.tsx
│     └─ turntable/TurntableRunView.tsx
└─ workspace/runs/<run_id>/
```

`colmap.py / openmvs.py / brush.py / blender.py` 是底层工程能力，不属于某一种采集方式，因此保持在共享 pipeline 层。

---

## New Run

无需额外的 Run 选择页。

Studio 的 `+ New Run` 一次选择：

```text
Video
Run ID
Capture Method
```

Capture Method：

```text
Orbit Camera
Object fixed / camera moves
Stable

Turntable
Camera fixed / rigid object rotates
Research
```

Capture Method 在 source 导入 / extract 后视为 Run 的不可变属性。选错采集方式时创建新的 Run，不在已有 Run 中途切换。

---

## Quick Start

```powershell
cd D:\Desktop\Videoto3D
python Videoto3D.py gui
```

环境：

```powershell
python Videoto3D.py env status
python Videoto3D.py env repair core
python Videoto3D.py env repair seg
python Videoto3D.py env repair gui
python Videoto3D.py doctor
```

Run：

```powershell
python Videoto3D.py runs list
python Videoto3D.py runs show --run <run_id>
```

Orbit Camera：

```powershell
python Videoto3D.py run extract --run orbit_01 --input .\video.mp4 --capture-mode orbit_camera
python Videoto3D.py run mask --run orbit_01
python Videoto3D.py run sparse --run orbit_01
```

Turntable：

```powershell
python Videoto3D.py run extract --run turntable_01 --input .\video.mp4 --capture-mode turntable
python Videoto3D.py run mask --run turntable_01
python Videoto3D.py run sparse --run turntable_01
```

---

## Outputs

```text
workspace/runs/<run_id>/output/<run_id>.glb
workspace/runs/<run_id>/output/<run_id>_splat.ply
```

V1.4 保留 GLB / PLY 两种最终资产形式，但 Turntable 的 Geometry / Gaussian 上游允许独立演化。

---

## Workspace Contract

所有项目工作流数据仍只写入：

```text
workspace/runs/<run_id>/
```

不得向 COLMAP、OpenMVS、Brush、Blender 等外部软件安装目录写入项目数据。

---

## V1.3 Turntable History

V1.3.x 先后实验了：

```text
mask-guided Turntable features
known virtual camera poses
adaptive / free-span angle graph
constrained Essential fitting
pose A/B benchmark
sequential vs exhaustive matching benchmark
```

这些实验确认：**Turntable 不是 Orbit Camera SfM 的一个参数开关，而是独立的 object-centric motion / pose 问题。**

历史快照：

```text
branch: snapshot/pre-v1.4-20260818
tag:    pre-v1.4-experiments-20260818
```

---

## Development / Verification

当前 V1.4 分支：

```text
feat/v1.4-capture-workflows
```

验证：

```powershell
python -m pytest -q
npm --prefix gui run typecheck
npm --prefix gui run build
git diff --check
```

在完整验证以及真实 Orbit Camera 回归完成前，不合并 `main`。

---

## V1.4 Canonical CLI Reference

The command registry is the source of truth. Current canonical commands:

```text
python Videoto3D.py env status
python Videoto3D.py env repair <core|seg|gui>
python Videoto3D.py gui
python Videoto3D.py doctor
python Videoto3D.py route mesh --run <run_id> [--input <video>] [--capture-mode orbit_camera|turntable] [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1] [--output-name name.glb] [--output <path>]
python Videoto3D.py route splat --run <run_id> [--input <video>] [--capture-mode orbit_camera|turntable] [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]
python Videoto3D.py run extract --run <run_id> --input <video> [--capture-mode orbit_camera|turntable]
python Videoto3D.py run mask --run <run_id> [--box x0,y0,x1,y1]
python Videoto3D.py run sparse --run <run_id>
python Videoto3D.py run mesh --run <run_id> [--undistort-max-image-size 2000] [--dense-resolution-level 0] [--dense-number-views 0] [--dense-max-threads 0] [--refine-resolution-level 1]
python Videoto3D.py run glb --run <run_id> [--output-name name.glb] [--output <path>]
python Videoto3D.py run splat --run <run_id> [--steps 30000] [--max-splats 2000000] [--max-resolution 1280] [--foreground-ratio 0.6] [--min-foreground-observations 2] [--cleanup-ratio 0.7] [--cleanup-min-views 3]
python Videoto3D.py view masks --run <run_id>
python Videoto3D.py view sparse --run <run_id>
python Videoto3D.py view splat-init --run <run_id>
python Videoto3D.py view mesh (--run <run_id> | --path <obj>)
python Videoto3D.py view glb (--run <run_id> | --path <glb>)
python Videoto3D.py view splat (--run <run_id> | --path <ply>)
python Videoto3D.py quality --run <run_id>
python Videoto3D.py runs list
python Videoto3D.py runs show <run_id>
```

## Preserved Engineering Contracts

- Bug/incident registry: `docs/bugs`
- GUI control application: `gui/control`
- Reusable 3D viewer package: `gui/viewer`
- OpenMVS mask naming: `frame_0001.mask.png`
- Splat object sparse report: `object_sparse_report.json`
- Raw Brush SPLAT: `splat/raw/<run_id>_raw.ply`
- Final cleanup/quality report: `quality/report.json`

Mesh and Splat remain independent downstream routes. Viewer processes are
detached from the terminal. Changing only Splat cleanup thresholds does not
require retraining Brush.
