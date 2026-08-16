# Videoto3D

> Video / Images → Mesh GLB + Gaussian Splat PLY  
> 一个本地优先、可自动配置环境、通过 Web GUI 操作的自动化 3D 重建工具。

---

## 1. 项目目标

`Videoto3D` 的目标是把传统上需要用户分别操作 FFmpeg、COLMAP、OpenMVS、Brush、Blender 的复杂三维重建流程，整合成一个统一的软件项目。

最终用户只需要：

```bash
python app.py
```

程序即自动完成：

```text
启动
 ↓
检查运行环境
 ↓
检查依赖软件
 ↓
发现已安装软件
 ↓
缺少依赖？
 ├─ 是 → 自动下载 / 让用户选择已有路径 / 给出人工安装指引
 └─ 否
 ↓
验证依赖是否能够正常执行
 ↓
启动 Videoto3D Backend
 ↓
自动打开本地 Web GUI
 ↓
用户上传视频 / 图片
 ↓
选择重建方式和质量
 ↓
自动执行完整重建流水线
 ↓
网页预览结果
 ↓
输出 GLB / PLY
```

### 核心设计原则

1. **用户正常使用只需要一个启动命令。**
2. **所有工作流数据必须保存在 `Videoto3D` 工作空间中。**
3. **禁止向 COLMAP、OpenMVS、Brush、Blender 等外部软件目录写入输入、中间数据或输出结果。**
4. **第三方工具只是计算引擎，不拥有项目数据。**
5. **环境配置应尽可能自动化。**
6. **无法自动配置时，应明确告诉用户缺少什么以及如何解决。**
7. **Local-first：第一阶段所有计算均在用户本机完成。**
8. **GUI 使用浏览器，本地计算使用用户 CPU/GPU。**
9. **CLI、Web GUI 与未来 Cloud 版本共用同一套 Pipeline Core。**
10. **每个重建任务可复现、可追踪、可清理。**

---

# 2. 项目最终定位

Videoto3D 不只是一个针对 `hlw.glb` 的脚本。

项目正式定位：

> **An automated local-first 3D reconstruction pipeline that converts videos or image sequences into web-ready Mesh and Gaussian Splat assets.**

主要能力：

- Video → Frames
- Image preprocessing
- Camera reconstruction
- Traditional Mesh reconstruction
- Gaussian Splat reconstruction
- Mesh optimization
- GLB export
- PLY export
- Environment diagnosis
- Dependency management
- Local Web GUI
- Result preview
- Reproducible project workspace

---

# 3. 总体技术路线

```text
                  Video / Images
                        │
                        ▼
                Frame Extraction
                    FFmpeg
                        │
                        ▼
               Image Preprocessing
                  Python/OpenCV
                        │
                        ▼
                    COLMAP
                        │
            Camera Pose + Sparse 3D
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
         Mesh Route           Gaussian Route
             │                     │
          OpenMVS                Brush
             │                     │
     Dense Point Cloud       Gaussian Training
             │                     │
       Mesh Reconstruction        │
             │                     │
       Mesh Refinement            │
             │                     │
       Mesh Texturing             │
             │                     │
          Blender                 │
             │                     │
      Web Optimization            │
             │                     │
             ▼                     ▼
           .glb                   .ply
```

---

# 4. 两条重建路线

## 4.1 Mesh Route

目标：

```text
Video
 ↓
COLMAP
 ↓
OpenMVS
 ↓
Blender
 ↓
model.glb
```

主要用于：

- Web 3D
- Three.js
- `<model-viewer>`
- Blender
- 游戏引擎
- AR / VR
- 后续编辑

核心输出：

```text
.glb
```

---

## 4.2 Gaussian Route

目标：

```text
Video
 ↓
COLMAP
 ↓
Brush
 ↓
model_splat.ply
```

主要用于：

- 高视觉保真展示
- Gaussian Splat Viewer
- Brush Viewer
- WebGPU 3D 展示
- 数字场景展示

核心输出：

```text
.ply
```

---

# 5. GLB 与 PLY 同时保留

Videoto3D 默认推荐：

```text
Output Mode

○ Mesh
○ Gaussian
● Both
```

最终一个任务可能产生：

```text
outputs/

model.glb
model_high.glb
model_mobile.glb

model_splat.ply

preview.jpg

reconstruction.json
```

GLB 和 Gaussian PLY 不互相替代。

---

# 6. 工作空间设计

整个项目位于：

```text
Videoto3D/
```

所有工作流数据都必须在该目录体系内。

建议结构：

```text
Videoto3D/
│
├── app.py
├── PLAN.md
├── README.md
├── LICENSE
├── pyproject.toml
│
├── videoto3d/
│   │
│   ├── doctor/
│   ├── installer/
│   ├── pipeline/
│   ├── adapters/
│   ├── backend/
│   ├── web/
│   └── config/
│
├── runtime/
│   ├── ffmpeg/
│   ├── colmap/
│   ├── openmvs/
│   ├── brush/
│   └── blender/
│
├── workspace/
│   │
│   ├── input/
│   │
│   ├── runs/
│   │   └── <run_id>/
│   │       ├── source/
│   │       ├── frames/
│   │       ├── masks/
│   │       ├── colmap/
│   │       ├── openmvs/
│   │       ├── brush/
│   │       ├── blender/
│   │       ├── logs/
│   │       └── metadata.json
│   │
│   ├── output/
│   └── cache/
│
├── config/
│   ├── settings.json
│   └── tools.json
│
├── tests/
├── docs/
└── scripts/
```

---

# 7. 数据隔离原则

这是 Videoto3D 的强制规则。

例如 COLMAP 不允许使用：

```text
C:\Program Files\COLMAP\data
```

作为 workspace。

正确方式：

```text
Videoto3D/
└── workspace/
    └── runs/
        └── 2026xxxx_xxxxxx/
            └── colmap/
```

OpenMVS：

```text
Videoto3D/workspace/runs/<run_id>/openmvs/
```

Brush：

```text
Videoto3D/workspace/runs/<run_id>/brush/
```

Blender：

```text
Videoto3D/workspace/runs/<run_id>/blender/
```

所有第三方软件只能：

```text
读取 Videoto3D workspace
+
向 Videoto3D workspace 写入
```

不能污染：

- 第三方软件安装目录
- 用户桌面
- Documents
- 系统 Temp
- 其他 GitHub 项目

如果第三方工具必须使用临时目录，应显式指定：

```text
Videoto3D/workspace/cache/
```

---

# 8. runtime 与 workspace 严格分离

```text
runtime/
```

只存放：

```text
第三方程序
binary
DLL
model/runtime dependency
```

禁止出现：

```text
照片
视频
COLMAP database
点云
Mesh
PLY
GLB
日志
```

工作流数据统一进入：

```text
workspace/
```

---

# 9. Git 管理原则

以下内容进入 Git：

```text
source code
README
PLAN
docs
tests
configuration templates
installer manifests
version manifests
```

以下内容不进入 Git：

```text
runtime/
workspace/
user config
logs
large models
temporary files
GLB
PLY
videos
photos
```

`.gitignore` 至少包含：

```gitignore
runtime/
workspace/
config/settings.json

*.log
*.tmp
*.glb
*.ply
*.mp4
*.mov
```

演示文件应单独规划 GitHub Release 或网站 CDN。

---

# 10. 唯一用户入口

正常用户不需要记：

```text
check.py
doctor.py
web.py
build.py
pipeline.py
```

唯一公开入口：

```bash
python app.py
```

该命令承担 Bootstrap 职责。

内部执行：

```text
app.py
 │
 ├─ Step 1  Bootstrap
 ├─ Step 2  Environment Doctor
 ├─ Step 3  Tool Discovery
 ├─ Step 4  Dependency Resolution
 ├─ Step 5  Tool Verification
 ├─ Step 6  Backend Startup
 └─ Step 7  Open Browser
```

---

# 11. Python 前置条件

V1 阶段暂定最低人工前置条件：

```text
Python
Git
```

执行：

```bash
python app.py
```

未来可以增加：

```text
Videoto3D.exe
```

作为 Bootstrap Launcher。

但 EXE 仅负责：

```text
启动
检查环境
启动 Web Backend
```

GUI 仍然使用浏览器。

因此最终产品仍属于：

> Local Web Application

而不是传统 Desktop GUI。

---

# 12. Environment Doctor

首次执行：

```bash
python app.py
```

自动检查：

## System

```text
OS
Architecture
CPU
RAM
Disk Space
```

## GPU

```text
GPU Vendor
GPU Model
VRAM
Driver
CUDA / WebGPU capability
```

## Core

```text
Python
Git
FFmpeg
```

## Reconstruction

```text
COLMAP
OpenMVS
Brush
Blender
```

结果：

```text
Videoto3D Environment Doctor
────────────────────────────────

System
✓ Windows 11 x64

Hardware
✓ CPU
✓ RAM
✓ NVIDIA GPU
✓ GPU Driver
✓ Disk Space

Core
✓ Python
✓ Git
✓ FFmpeg

Reconstruction
✓ COLMAP
✗ OpenMVS
✓ Brush
✗ Blender

Environment incomplete.
```

---

# 13. Dependency Discovery

对于每一个软件：

```text
1. 检查项目 runtime
2. 检查保存的自定义路径
3. 检查 PATH
4. 检查常见系统安装路径
5. 验证 executable
6. 检查版本
```

例如：

```text
COLMAP found:

D:\Software\COLMAP\COLMAP.bat

Version:
3.x

Status:
Compatible ✓
```

---

# 14. 自动安装逻辑

如果发现缺失：

```text
OpenMVS missing
```

界面提供：

```text
Install automatically
Choose existing installation
Skip
View instructions
```

推荐路径：

```text
Videoto3D/runtime/openmvs/
```

自动安装步骤：

```text
下载
 ↓
校验 checksum
 ↓
解压
 ↓
发现 executable
 ↓
执行 version test
 ↓
保存路径
```

---

# 15. 无法自动安装时

禁止只显示：

```text
ERROR
```

必须告诉用户：

```text
OpenMVS could not be installed automatically.

Reason:
No compatible prebuilt package was found.

Videoto3D needs:
OpenMVS >= ...

Options:

1. Install OpenMVS manually
2. Select an existing OpenMVS installation
3. Disable Mesh reconstruction

[Installation Guide]

After installation:
Restart Videoto3D.
```

---

# 16. Environment Doctor 不应成为第二条用户命令

不要求用户执行：

```bash
python doctor.py
```

正常流程永远是：

```bash
python app.py
```

Doctor 是启动流程的一部分。

网页 Settings 中可以额外提供：

```text
Run Environment Check
```

供高级用户重新检查。

---

# 17. Local Web GUI

环境检查完成后：

```text
Starting Videoto3D...

Backend:
127.0.0.1

Opening browser...
```

浏览器自动进入：

```text
http://127.0.0.1:<port>
```

---

# 18. GUI 第一版页面

## Home

```text
Videoto3D

Video & Images → 3D

Drop video or images here

[ Browse ]

Reconstruction

● Both
○ Mesh
○ Gaussian

Quality

○ Draft
● Standard
○ High

[ Start Reconstruction ]
```

---

# 19. 重建过程页面

```text
Videoto3D

Project: hlw

Input
✓ Video loaded

Preprocessing
✓ Extract Frames
✓ Image Validation
✓ Image Filtering

Camera Reconstruction
✓ COLMAP Features
✓ Matching
✓ Sparse Reconstruction

Mesh Route
✓ Dense Reconstruction
72% Mesh Reconstruction
○ Texture
○ GLB

Gaussian Route
46% Brush Training

Logs
[ View ]
```

---

# 20. 输出页面

```text
Reconstruction Complete
```

显示：

## Mesh

```text
model.glb

Preview
File Size
Vertices
Triangles
Textures

[ Open ]
[ Export ]
```

## Gaussian

```text
model_splat.ply

Preview
File Size
Gaussian Count

[ Open ]
[ Export ]
```

同时提供：

```text
Open Output Folder
```

---

# 21. Run ID

每次任务必须生成独立：

```text
run_id
```

例如：

```text
20260816_001_hlw
```

所有数据：

```text
workspace/runs/20260816_001_hlw/
```

这样可以：

- 避免不同任务互相覆盖
- 支持断点恢复
- 保留日志
- 支持重新执行部分 Pipeline
- 对比不同参数
- 快速删除项目

---

# 22. Pipeline 状态系统

每个阶段：

```text
PENDING
RUNNING
SUCCESS
FAILED
SKIPPED
```

例如：

```json
{
  "frames": "SUCCESS",
  "colmap": "SUCCESS",
  "openmvs": "RUNNING",
  "brush": "RUNNING",
  "blender": "PENDING"
}
```

Web GUI 根据状态更新进度。

---

# 23. Adapter 架构

不要在 Pipeline 中直接写大量 shell 命令。

为每个外部程序建立 Adapter：

```text
FFmpegAdapter
COLMAPAdapter
OpenMVSAdapter
BrushAdapter
BlenderAdapter
```

统一接口，例如：

```text
detect()
version()
validate()
run()
cancel()
```

这样未来替换某个软件不会影响整个 Pipeline。

---

# 24. V0 —— 工程验证

V0 暂时不开发完整自动化。

目标：

> 使用真实 `hlw` 数据验证所有外部软件确实能够完成预期任务。

测试：

```text
视频
 ↓
FFmpeg
 ↓
COLMAP
```

随后分叉：

```text
COLMAP
├── OpenMVS
│     ↓
│   Blender
│     ↓
│   hlw.glb
│
└── Brush
      ↓
    hlw_splat.ply
```

V0 成功标准：

- FFmpeg 视频抽帧成功
- COLMAP 相机重建成功
- OpenMVS 接受 COLMAP 数据
- OpenMVS 产生可用 Mesh
- Blender 能导入并处理 Mesh
- Blender 成功导出 GLB
- Brush 接受同一组 COLMAP 数据
- Brush 成功训练 Gaussian Splat
- Brush 导出 PLY
- GLB 可以网页查看
- Gaussian PLY 可以正确查看
- 所有工作数据均位于 Videoto3D workspace

---

# 25. V0 数据目录

即使是人工验证也必须遵守正式数据规则：

```text
Videoto3D/
└── workspace/
    └── runs/
        └── hlw_v0/
            ├── source/
            ├── frames/
            ├── colmap/
            ├── openmvs/
            ├── brush/
            ├── blender/
            ├── logs/
            └── output/
```

禁止为了方便直接将照片复制进：

```text
COLMAP/
Brush/
OpenMVS/
Blender/
```

软件安装目录。

---

# 26. V1 —— Core + Environment Doctor

完成：

- 项目目录结构
- Config
- Environment Doctor
- Tool Discovery
- Tool Validation
- Dependency Installer
- FFmpeg Adapter
- COLMAP Adapter
- OpenMVS Adapter
- Brush Adapter
- Blender Adapter

统一入口：

```bash
python app.py
```

此时即使 Web GUI 尚未完善，也不再要求用户分别运行多个脚本。

---

# 27. V2 —— Automated Pipeline

完成：

```text
Video
 ↓
Frames
 ↓
Preprocess
 ↓
COLMAP
 ↓
OpenMVS / Brush
 ↓
Blender
 ↓
Outputs
```

实现：

- Pipeline orchestration
- Run state
- Logs
- Retry
- Cancellation
- Error propagation
- Output validation

---

# 28. V3 —— Local Web GUI

实现：

```text
Browser
 ↓
Local Backend
 ↓
Pipeline Core
 ↓
Local CPU/GPU
```

用户不再接触具体命令。

GUI 完成：

- Input
- Settings
- Reconstruction
- Progress
- Logs
- Preview
- Output
- Environment
- History

---

# 29. V4 —— GitHub Release

GitHub 仓库：

```text
Videoto3D
```

README 结构：

```text
# Videoto3D

Demo

Overview

Features

How It Works

Architecture

Requirements

Quick Start

Environment Doctor

Reconstruction Modes

Workspace

Outputs

Troubleshooting

Roadmap

Contributing

License
```

Quick Start 应保持非常短：

```bash
git clone <repo>
cd Videoto3D
python app.py
```

不在首页要求用户记忆更多命令。

---

# 30. GitHub Demo

README 顶部展示：

```text
Input Video
     ↓
Videoto3D GUI
     ↓
Interactive Model
```

推荐：

```text
15~30 秒 GIF
+
完整 Demo Video
```

Demo 内容：

1. 打开 Videoto3D
2. Environment Check
3. 上传视频
4. Start Reconstruction
5. 查看 Pipeline
6. Mesh Result
7. Gaussian Result
8. 网站中展示结果

---

# 31. V5 —— 个人网站集成

个人网站 Projects 不直接堆放所有项目。

新增一级入口：

```text
Projects

├── Research Projects
├── Hardware / IC Projects
├── Embodied AI Projects
└── 编程项目合集
```

---

# 32. 编程项目合集

点击：

```text
编程项目合集
```

进入：

```text
/projects/software
```

页面展示多个 Software Project Card。

其中：

```text
┌───────────────────────────────┐
│                               │
│          Videoto3D            │
│                               │
│ Video / Images → 3D           │
│                               │
│ Automated reconstruction      │
│ pipeline with Mesh and        │
│ Gaussian Splat output.        │
│                               │
│ Python · COLMAP · OpenMVS     │
│ Brush · Blender · Web         │
│                               │
│ View Project →                │
└───────────────────────────────┘
```

---

# 33. Videoto3D 项目详情页

点击卡片：

```text
/projects/software/videoto3d
```

进入专属详情页。

页面结构：

```text
Videoto3D

Automated Video-to-3D Reconstruction
```

顶部按钮：

```text
[ GitHub Repository ]

[ Demo Video ]
```

---

# 34. 项目详情页内容

## Hero

展示：

```text
Video
 ↓
Videoto3D
 ↓
GLB + Gaussian Splat
```

## Demo Video

完整展示：

```text
输入视频
↓
运行软件
↓
重建
↓
最终结果
```

## Problem

说明传统三维重建：

- 软件众多
- 环境复杂
- 依赖复杂
- 命令复杂
- 数据目录混乱

## Solution

展示 Videoto3D：

```text
Environment Doctor
↓
Automatic Setup
↓
Local Web GUI
↓
Automated Pipeline
↓
Mesh + Gaussian
```

## Architecture

展示：

```text
FFmpeg
↓
COLMAP
├─ OpenMVS → Blender → GLB
└─ Brush → PLY
```

## Results

展示：

```text
Mesh
vs
Gaussian
```

## GitHub

最后提供：

```text
View Source on GitHub →
```

---

# 35. 个人网站职责

个人网站重点：

> 展示项目价值和最终效果。

内容包括：

- 项目介绍
- Demo
- 技术架构
- 结果
- 技术亮点
- GitHub 链接

不承担完整安装文档。

---

# 36. GitHub 职责

GitHub 重点：

> 展示工程实现以及如何使用。

包括：

- Source Code
- Setup
- Architecture
- Dependencies
- Workspace
- Troubleshooting
- Issues
- Releases
- Roadmap

---

# 37. V6 —— Web Preview

未来可以直接在个人网站项目详情页提供：

```text
GLB Interactive Viewer
```

用户可以：

- Rotate
- Zoom
- Pan

Gaussian Splat 也可以增加：

```text
Gaussian Viewer
```

最终实现：

```text
Mesh      Gaussian
  ↓           ↓
[Interactive comparison]
```

---

# 38. V7 —— Cloud Mode

这是远期版本，不属于当前开发范围。

未来架构：

```text
Browser
 ↓
Videoto3D Cloud
 ↓
Job Queue
 ↓
GPU Worker
 ↓
Storage
 ↓
Result
```

Local 与 Cloud 必须尽量共用：

```text
Pipeline Core
Adapter
Config
Job Model
```

---

# 39. 暂不开发

当前明确不做：

- 用户系统
- 登录
- 支付
- GPU 云平台
- 分布式计算
- 多用户队列
- 在线对象存储
- 原生复杂桌面 GUI
- 移动端 App

先把核心 reconstruction 做可靠。

---

# 40. 开发顺序

严格按照：

```text
V0
真实工作流验证

↓

V1
Environment Doctor
Tool Adapter
统一启动入口

↓

V2
Pipeline 自动化

↓

V3
Local Web GUI

↓

V4
GitHub Release

↓

V5
个人网站集成

↓

V6
Interactive Web Preview

↓

V7
Cloud Mode
```

禁止在 V0 未验证前大规模开发 UI 或安装器。

---

# 41. 当前第一目标

现在的目标不是：

> “开发 Videoto3D。”

而是：

> **证明 Videoto3D 所依赖的核心技术路线真实可行。**

因此下一阶段只处理：

```text
Videoto3D/workspace/runs/hlw_v0/
```

并得到两个核心文件：

```text
hlw.glb
```

以及：

```text
hlw_splat.ply
```

只有这两个结果达到可接受质量后，才开始自动化封装。

---

# 42. 第一阶段验收标准

## Mesh

- 人物主体完整
- 无严重断裂
- 无大面积错误 Mesh
- Texture 正常
- Blender 正常加载
- GLB 正常导出
- 浏览器正常显示

## Gaussian

- Brush 正常训练
- 主体完整
- 新视角无严重 artifact
- PLY 正常保存
- Viewer 正常加载

## Engineering

- 数据没有写入第三方软件目录
- 所有中间文件可定位
- 每一步命令被记录
- 软件版本被记录
- 参数被记录
- 错误和解决办法被记录

这些记录最终直接成为 Videoto3D 自动化 Pipeline 的基础。

---

# 43. 项目核心原则总结

Videoto3D 应始终遵循：

```text
One Command
One Workspace
Local First
Web GUI
Reproducible Pipeline
External Tools as Engines
Mesh + Gaussian
GitHub First
Portfolio Ready
Cloud Ready
```

其中最重要的三条：

> **One Command**  
> 用户正常使用只执行 `python app.py`。

> **One Workspace**  
> 所有输入、中间结果和输出均属于 Videoto3D workspace。

> **External Tools as Engines**  
> COLMAP、OpenMVS、Brush、Blender 只作为计算后端，不拥有 Videoto3D 的数据和用户体验。