# Videoto3D 工作流视频录制指南

> 目标：录制一套既能证明 Videoto3D 完整工作流、又适合 GitHub README 和个人网站展示的素材。主 README Demo 建议 60–90 秒；另保留一条 8–15 分钟的完整讲解版。

---

## 1. 这次录制要证明什么

README 主视频不要把重点放在“终端跑了一堆命令”，而要让观看者快速理解：

```text
一个视频
  ↓
抽帧 + SAM2 主体分割
  ↓
COLMAP 恢复相机与稀疏几何
  ↓
├─ OpenMVS → Dense → Mesh → Texture → GLB
└─ Brush → Raw Gaussian → SAM2 Cleanup → Clean PLY
```

V1.2.0 的 Artifact Inspector 正好负责把这些中间结果可视化，因此录制时应该让中间产物成为主角。

---

## 2. 录制前准备

### 2.1 先完成环境预热

在录屏前一天或正式录屏前先运行一次：

```powershell
cd D:\Desktop\Videoto3D
python app.py env status
python app.py doctor
python app.py gui
```

目的：

- 确认 `env/core`、`env/seg`、`env/gui` 都已就绪；
- 确认 FFmpeg / COLMAP / OpenMVS / Brush / Blender 可用；
- 让 GUI 前端提前完成 npm build；
- 避免正式录制时出现首次环境下载、依赖安装或前端构建等待。

### 2.2 保留一个“已完成的漂亮 Run”

正式从零录制一个新 Run，但同时保留一个已经成功完成 Mesh + Splat 的 Run，用于最后补录：

- GLB 旋转镜头；
- Clean Splat 旋转镜头；
- Raw ↔ Clean Splat 对比；
- Raw Mesh ↔ Refined Mesh 对比；
- Quality Report。

这样即使正式长流程某个阶段临时失败，也不会毁掉整次素材录制。

### 2.3 新 Run 命名

不要删除现有实验。建议新建：

```text
ceramics_doll_demo_v120
```

或：

```text
workflow_demo_001
```

录制完成后保留它，后续 README 数据和截图都来自同一个 Run，叙事最一致。

---

## 3. OBS 推荐设置

使用 OBS Studio。

### 画布与输出

```text
Base Canvas       1920 × 1080
Output Resolution 1920 × 1080
FPS               30
Recording Format  MKV（录完 Remux 为 MP4）或直接 MP4
Encoder           H.264 硬件编码（NVIDIA 可用 NVENC）
```

如果已经熟悉 OBS，也可以直接录 MP4；MKV 的优点是异常退出时更不容易整段损坏。

### 录什么窗口

README 主素材优先只录：

```text
浏览器中的 Videoto3D Studio
```

长教程可以补录：

```text
PowerShell / Anaconda Prompt
```

主 Demo 不建议把桌面、聊天软件、文件管理器和通知一起录进去。

### 浏览器整理

录制前：

- 关闭书签栏（如果会泄露个人信息）；
- 关闭无关标签页；
- 浏览器缩放建议 100%；
- 关闭系统通知；
- 使用 1920×1080 或相近窗口比例；
- 鼠标移动尽量慢且有目的；
- Artifact 3D Viewer 中尽量使用平滑的小幅旋转，不要高速乱甩模型。

---

## 4. 最推荐的录制方法：先录 Master，再剪 Demo

不要试图“一遍录出 90 秒成片”。

先录一条完整 Master：

```text
从 New Run 到 Mesh + Splat + Artifact Inspector + Quality
```

真实等待过程也录下来。

后期再：

- 删除无意义等待；
- 对 COLMAP / OpenMVS / Brush 长阶段做 8× / 16× / 32× 加速；
- 保留 Progress Card 出现 1–3 秒，让别人知道计算确实发生过；
- 从同一个 Master 剪出 60–90 秒 README Demo。

原始 Master 放：

```text
D:\Desktop\Videoto3D\recordings\
```

该目录已加入 `.gitignore`，不要把原始几 GB 视频提交到 GitHub。

---

## 5. 完整工作流 Master 的录制顺序

### Shot 01 — 输入视频

时长：5–10 秒。

展示原始拍摄视频，最好能明显看出相机围绕主体运动。

画面目的：让观看者知道 3D 的输入只是一段普通视频。

---

### Shot 02 — New Run

在 Studio 首页：

1. 点击 `New Run`；
2. 输入 Run ID；
3. 选择视频；
4. 创建 Run。

保留上传/Extract Progress Card 的一小段。

---

### Shot 03 — Frames 中间产物

抽帧结束后打开：

```text
Pipeline Artifacts
→ Shared
→ Frames
→ View Artifact
```

拖动帧滑块，快速浏览前 / 中 / 后三个视角。

录制重点：

> 视频已经被转成多视角静态 RGB 帧。

---

### Shot 04 — ROI + SAM2

回到对象选择：

1. 在第一帧框选主体；
2. 点击 `Generate Masks`；
3. Progress Card 显示 SAM2 进度；
4. 等待完成。

---

### Shot 05 — Mask Original / Mask / Overlay

打开：

```text
Pipeline Artifacts
→ Shared
→ SAM2 Masks
```

依次点击：

```text
Original
Mask
Overlay
```

然后拖动到 3–4 个不同视角检查 Mask。

这是 README 最值得保留的镜头之一，因为它直接解释主体隔离来自哪里。

---

### Shot 06 — 启动 Mesh Route

点击：

```text
Run Mesh
```

录制 Progress Stepper：

```text
Sparse
→ Dense
→ Reconstruct
→ Refine
→ Texture
→ GLB
```

长等待后期加速。

---

### Shot 07 — COLMAP Sparse

Shared Sparse 完成后打开：

```text
Pipeline Artifacts
→ Shared
→ COLMAP Sparse
```

在 Point Cloud Viewer 中：

- Fit；
- 小幅旋转；
- 展示 sparse points 数量；
- 然后切到 Quality Report，短暂展示 registered images / reprojection error。

说明重点：

> COLMAP 已从多视角图像恢复 3D 特征几何和相机关系。

V1.2.0 浏览器预览当前重点显示 sparse points；完整相机 frustum 可视化仍可使用 COLMAP Viewer，后续版本再考虑进入 Web Inspector。

---

### Shot 08 — Dense Cloud

打开：

```text
Mesh Route
→ Dense Cloud
```

和刚才 Sparse 镜头形成明显对比。

README 剪辑里可以直接做：

```text
Sparse → Dense
```

这是解释 MVS 最直观的画面。

---

### Shot 09 — Raw Mesh ↔ Refined Mesh

分别打开 Raw Mesh 和 Refined Mesh，之后点击：

```text
Compare · Raw Mesh ↔ Refined Mesh
```

录制左右 A/B 对比。

展示重点：

- Point Cloud 已经变成三角面；
- Refine 阶段进一步调整了几何表面。

---

### Shot 10 — Texture Atlas

打开：

```text
Mesh Route
→ Texture Atlas
```

如果存在多个 atlas，用滑块切换。

这是很好的教学镜头：最终模型的外观并不是“模型自己有颜色”，而是由照片投影形成纹理图集，再通过 UV 映射到 Mesh。

---

### Shot 11 — Final GLB

打开：

```text
Mesh Route
→ Final GLB
```

推荐镜头动作：

1. `Fit`；
2. `Iso`；
3. 手动慢速旋转约 180°；
4. 停住 1 秒；
5. 可补一个 `Auto Rotate` 镜头。

这是 Mesh Route 的最终 Beauty Shot。

---

### Shot 12 — 启动 Splat Route

点击：

```text
Run Splat
```

保留：

```text
Object Sparse
Brush Training
Cleanup
```

进度画面。

Brush 30k 训练非常适合后期 16× / 32× 加速，同时保留 iteration 数字变化。

---

### Shot 13 — Object Sparse

打开：

```text
Splat Route
→ Object Sparse
```

与 Shared COLMAP Sparse 对照。

说明重点：

> 相机仍来自完整 RGB SfM，但用于 Brush 初始化的 3D points 已根据 SAM2 Mask 过滤成主体优先点集。

---

### Shot 14 — Raw Splat

打开：

```text
Splat Route
→ Raw Splat
```

慢速旋转，特别保留物体周围仍存在 halo / 背景 Gaussian 的区域。

不要只展示最漂亮角度；这里的意义是给下一步 Cleanup 提供对照。

---

### Shot 15 — Raw ↔ Clean Splat

点击：

```text
Compare · Raw Splat ↔ Clean Splat
```

这是整条 Splat Route 最有说服力的镜头。

建议录 5–8 秒：

```text
Raw                        Clean
背景 / halo Gaussian   →   主体更干净
```

---

### Shot 16 — Final Clean Splat

单独打开 Clean Splat：

1. Fit；
2. 调整到最好的朝向；
3. 慢速旋转；
4. 停住。

这是 Splat Route 的最终 Beauty Shot。

---

### Shot 17 — Quality Report

最后短暂向下滚动到 Quality：

```text
Frames / Masks
COLMAP registration
Sparse Points
Reprojection Error
Mesh Vertices / Faces
Raw / Clean Splats
Cleanup removed ratio
```

不需要停太久，2–4 秒即可。

---

## 6. 60–90 秒 README Hero Demo 剪辑表

推荐成片节奏：

```text
00–05 s  Input video
05–12 s  New Run / import
12–20 s  Frames → ROI
20–29 s  SAM2 Original / Mask / Overlay
29–38 s  COLMAP Sparse
38–50 s  Dense → Raw Mesh → Refined Mesh → Texture Atlas
50–60 s  Final GLB beauty shot
60–70 s  Object Sparse → Brush progress → Raw Splat
70–80 s  Raw Splat ↔ Clean Splat
80–90 s  Final Mesh + Final Splat + Videoto3D title
```

如果成片超过 90 秒，优先删掉：

- 文件选择器过程；
- 长日志；
- 重复旋转；
- Paths & Runtime；
- 参数设置细节。

README 主 Demo 应展示“能力和结果”，而不是完整教程。

---

## 7. 8–15 分钟完整 Workflow 教程建议

长版可以加入讲解：

```text
1. 为什么抽帧
2. SAM2 Mask 为什么不直接替换 COLMAP RGB
3. COLMAP SfM：Feature / Match / Pose / Sparse
4. OpenMVS：Dense / Mesh / Refine / Texture
5. Gaussian Splat：Object Sparse / Brush / Cleanup
6. Quality Report 怎么判断失败发生在哪一步
7. Paths & Runtime 如何定位真实中间文件
```

知识内容可以直接参考：

```text
docs/guides/Videoto3D_Workflow_Knowledge_Framework.md
```

建议先录画面，再后期配音。这样说错一句不需要重新跑整个 3D 重建。

---

## 8. README 媒体文件怎么管理

建议仓库只保存轻量展示素材：

```text
docs/assets/demo/
├─ hero.png
├─ workflow-demo.gif        # 或小型 WebP
├─ artifacts.png
├─ mesh-result.png
└─ splat-result.png
```

原始视频放：

```text
recordings/
```

完整 MP4 建议放 GitHub Release、Bilibili、YouTube 或个人网站，再由 README 点击封面跳转。

不要把几百 MB / 几 GB 的录屏 Master 直接加入普通 Git 历史。此前 Git 仓库已经证明大型本地产物会严重干扰 push，因此这次录屏从一开始就和源码仓库隔离。

---

## 9. 把录屏转成 README GIF（可选）

如果 FFmpeg 已在 PATH：

```powershell
ffmpeg -i recordings\workflow_demo_cut.mp4 -vf "fps=12,scale=960:-2:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer" -loop 0 docs\assets\demo\workflow-demo.gif
```

如果 `ffmpeg` 命令不在 PATH，可从 Studio 的 **Paths & Runtime** 找到项目实际 FFmpeg 路径，再用完整路径执行。

GIF 如果太大：

- 缩短时长；
- scale 从 960 改为 800 / 720；
- fps 从 12 改为 10；
- 或改用静态封面 + 外部完整视频链接。

---

## 10. README 最终推荐展示结构

等视频和截图准备好以后，再更新 README，不要先提交空占位符。

推荐首屏：

```markdown
# Videoto3D

A local-first video-to-3D reconstruction studio.

Video → SAM2 + COLMAP → Mesh GLB / Gaussian Splat PLY

[Workflow Demo]

| Input | Mesh | Splat |
|---|---|---|
| video thumbnail | GLB screenshot | clean PLY screenshot |
```

接着展示：

```text
Pipeline
Features
Artifact Inspector
Results + Quality metrics
Quick Start
Installation
Technical Guide
```

并链接：

```text
docs/guides/Videoto3D_Workflow_Knowledge_Framework.md
```

---

## 11. 正式录制前检查表

```text
[ ] env status 全部 READY
[ ] doctor Required environment READY
[ ] GUI 已提前 build / 可正常启动
[ ] 浏览器通知与隐私信息已清理
[ ] 输入视频已复制到方便选择的位置
[ ] 新 Demo Run ID 已确定
[ ] 磁盘剩余空间充足
[ ] OBS 1080p / 30 FPS 测录 20 秒无问题
[ ] 已完成的漂亮 Run 仍保留用于补 Beauty Shot
[ ] recordings/ 已被 Git ignore
[ ] 不在录制过程中升级任何依赖
```

完成 Master 以后，先备份原始录屏，再开始剪辑。README 的最终媒体整合建议在 Demo 成片之后单独做一次小版本更新。


---

# 13. README 教学视频发布流程

根目录 `README.md` 已预留 `WORKFLOW_VIDEO_BEGIN / END` 区域。

教学视频录制完成后，推荐保留三份：

```text
recordings/
├─ workflow_master.mkv        # OBS 原始 Master
├─ workflow_tutorial.mp4      # 5–15 min 完整教学
└─ workflow_demo.mp4          # 60–90 s GitHub Showcase
```

`recordings/` 已被 `.gitignore` 排除。

## 推荐发布方式

### 完整版

优先：

```text
GitHub user attachment / Release
或
Bilibili / YouTube / 个人网站
```

如果使用 GitHub Web 上传视频，建议编码：

```text
MP4
H.264
1920×1080
30 FPS
AAC
```

GitHub 官方当前支持 MP4 / MOV / WebM，并推荐 H.264 以获得最大浏览器兼容性。

### README 短预览

不要把 5–15 分钟完整版直接作为普通 Git Blob 提交。

建议再剪：

```text
10–30 秒
720p
10–15 FPS
GIF / WebP
```

放到：

```text
docs/assets/demo/
```

README 推荐最终结构：

```markdown
[![Videoto3D Workflow Tutorial](docs/assets/demo/workflow-video-cover.png)](<FULL_VIDEO_URL>)

<!-- 如果 GitHub 上传生成了 user-attachments URL，也可以把该 URL 单独放在这里 -->
```

## 封面画面建议

用最终 Studio 截图做 16:9 封面，画面同时出现：

```text
左：Pipeline Artifacts
中：3D Viewer
右/下：Quality / Route 状态
```

标题：

```text
Videoto3D
Video → Mesh + Gaussian Splat
Full Workflow Tutorial
```

这样 README 首屏就能同时表达：

```text
有 GUI
有完整 Pipeline
有两条 3D Route
有中间产物
有最终结果
```

---

# 14. 已完成教学视频：V1.2.0 发布

最终教学视频已经录制完成：

```text
recordings/Videoto3D_Workflow_Tutorial_v1.2.0.mp4
```

当前信息：

```text
Duration: 4 min
Size:     ~17 MB
Format:   MP4 / H.264
```

该文件保留在本地 `recordings/`，不进入普通 Git 历史。

README 使用的正式 Release Asset 地址：

```text
https://github.com/HUliangwei/Videoto3D/releases/download/v1.2.0/Videoto3D_Workflow_Tutorial_v1.2.0.mp4
```

发布完成后，README 顶部的 Workflow Tutorial 封面会直接打开该视频。

发布顺序：

```text
1. 提交 V1.2.0 源码 / 文档
2. Push main
3. 创建并 Push v1.2.0 Tag
4. 创建 GitHub Release v1.2.0
5. 将 recordings/Videoto3D_Workflow_Tutorial_v1.2.0.mp4 上传为 Release Asset
6. 点击 README 教程封面验证链接
```

