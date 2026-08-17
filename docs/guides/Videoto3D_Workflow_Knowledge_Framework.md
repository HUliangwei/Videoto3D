# Videoto3D 工作流基础知识与数学框架

> 这份文档不是“命令说明书”，而是 Videoto3D 的技术学习主线。  
> 目标是让你从“我知道按按钮可以生成 3D”，逐步变成“我能解释每一个输入、输出、几何假设、优化目标、质量指标和失败原因”。

---

# 0. 如何阅读这份文档

建议分两遍。

**第一遍：只读第 1 章。**

先建立一条完整因果链：

```text
视频
为什么能变成多视角图像？
↓
为什么多视角图像可以恢复相机运动？
↓
为什么知道相机运动以后可以三角测量得到 3D？
↓
为什么 Sparse 还能变 Dense？
↓
为什么 Dense 可以变 Mesh？
↓
为什么 Gaussian Splat 不需要三角网格？
↓
SAM2 为什么既能辅助 Mesh，又能清理 Splat？
```

**第二遍：从第 2 章开始逐步看数学。**

每个阶段都按照：

```text
输入
→ 要解决的问题
→ 核心数学
→ Videoto3D 当前实现
→ 输出文件
→ Artifact Inspector 看什么
→ 常见失败
```

来解释。

---

# 1. 先完整走一遍：Video → 3D 到底发生了什么

## 1.1 视频本身不是 3D，真正有价值的是“视差”

假设摄像头围绕一个陶瓷娃娃移动。

对于娃娃鼻尖这个真实世界点 \(X\)，当摄像头位置改变时，它会投影到不同图像位置：

```text
Camera 1               Camera 2
    \                     /
     \                   /
      \                 /
            X
        娃娃鼻尖
```

如果我们能知道：

1. Camera 1 在哪里、朝哪里看；
2. Camera 2 在哪里、朝哪里看；
3. 鼻尖分别落在两张图哪个像素；

就能通过几何关系反推出 \(X\) 的三维位置。

因此：

> Video-to-3D 的基础不是“AI 从视频想象 3D”，而是 **Multi-View Geometry（多视图几何）**。

---

## 1.2 FFmpeg：把时间序列变成离散多视角图像

Videoto3D 当前默认：

```text
Video
↓ 4 FPS
frame_0001.jpg
frame_0002.jpg
...
```

这一步没有恢复任何 3D。

它只做：

\[
I(t) \longrightarrow \{I_1,I_2,\ldots,I_N\}
\]

其中每一张 \(I_i\) 都对应相机在某一时刻的观察。

---

## 1.3 SAM2：告诉后续阶段“哪个像素属于目标”

用户在第一帧画一个 Bounding Box：

```text
┌───────────────────────┐
│       background      │
│    ┌─────────────┐    │
│    │    object   │    │
│    └─────────────┘    │
└───────────────────────┘
```

SAM2 Video Predictor 将这个 Prompt 传播到后续帧，输出每帧二值 Mask：

\[
M_i(u,v)\in\{0,1\}
\]

其中：

\[
M_i(u,v)=
\begin{cases}
1,&\text{像素属于目标}\\
0,&\text{背景}
\end{cases}
\]

**重要：Videoto3D 不用 Masked RGB 取代 COLMAP 的原始 RGB。**

Shared SfM 仍然使用完整图像：

```text
RGB → COLMAP
Mask → 目标约束
```

原因后面会详细解释。

---

## 1.4 COLMAP：先回答“每张照片是从哪里拍的”

COLMAP 做的核心事情可以压缩成：

```text
图像特征
↓
跨帧匹配
↓
哪些像素是同一个真实点？
↓
相机之间是什么相对运动？
↓
Camera Pose + 3D Points
↓
Bundle Adjustment 联合优化
```

输出：

```text
Camera Intrinsics
Camera Poses
Sparse 3D Point Cloud
```

这一步叫：

> **Structure from Motion（SfM）**

---

## 1.5 为什么叫 Sparse

COLMAP 的 Feature 通常只存在于：

```text
角点
纹理明显处
高对比区域
```

所以得到的 3D 点不是表面每个位置都有。

结果可能像：

```text
      .   .
   .   .       .
 .   object  .
    .      .
```

而不是完整表面。

因此叫：

```text
Sparse Point Cloud
```

---

## 1.6 Shared 到这里结束

现在两条路线共享：

```text
Frames
Masks
Camera Intrinsics
Camera Poses
Sparse Geometry
```

然后分叉。

---

## 1.7 Mesh Route：从“稀疏几何”恢复传统三角网格

```text
COLMAP Undistort
↓
OpenMVS Dense Reconstruction
↓
Dense Point Cloud
↓
Mesh Reconstruction
↓
Triangle Mesh
↓
Mesh Refinement
↓
Texture Mapping
↓
Blender
↓
GLB
```

最终 GLB 是传统意义上的：

```text
Vertices + Triangles + Material + Texture
```

---

## 1.8 Splat Route：不建三角网格，而是优化大量 3D Gaussian

```text
COLMAP Cameras + Sparse
↓
SAM2 筛选目标 Sparse Points
↓
Brush 初始化 Gaussian
↓
多视角图像监督优化
↓
Raw Gaussian Splat
↓
SAM2 Multi-view Cleanup
↓
Clean Gaussian Splat
```

最终场景由很多椭球 Gaussian 组成。

它们不是三角面，但经过投影和透明度混合以后，可以从新视角重建出很逼真的图像。

---

## 1.9 最核心的一张图

```text
                         ┌──────── SAM2 masks ────────┐
                         │                            │
Video → Frames → COLMAP RGB SfM                      │
                  │                                  │
                  ├─ Cameras                         │
                  ├─ Sparse Points                   │
                  │                                  │
                  │                                  │
                  ├──── Mesh Route ◄─────────────────┤
                  │        ↓                         │
                  │      Dense                       │
                  │        ↓                         │
                  │      Mesh                        │
                  │        ↓                         │
                  │     Texture                      │
                  │        ↓                         │
                  │       GLB                        │
                  │                                  │
                  └──── Splat Route ◄────────────────┘
                           ↓
                    Object Sparse Init
                           ↓
                         Brush
                           ↓
                       Raw Splat
                           ↓
                  Multi-view Cleanup
                           ↓
                       Clean PLY
```

如果你已经理解这张图，后面所有章节都是在回答：

> “这里的每一个箭头，数学上到底做了什么？”

---

# 2. 预备知识：坐标系、向量和齐次坐标

整个 3D 重建最容易混乱的不是公式，而是：

> “这个点现在到底在哪个坐标系？”

## 2.1 世界坐标系 World Coordinate

真实 3D 点：

\[
\mathbf{X}_w=
\begin{bmatrix}
X_w\\Y_w\\Z_w
\end{bmatrix}
\]

例如娃娃鼻尖在重建世界里的坐标。

SfM 的世界坐标系不是物理世界预先规定好的，它由初始化过程确定。

---

## 2.2 相机坐标系 Camera Coordinate

同一个点在第 \(i\) 个相机下：

\[
\mathbf{X}_{c,i}=
\begin{bmatrix}
X_c\\Y_c\\Z_c
\end{bmatrix}
\]

通过旋转和平移：

\[
\mathbf{X}_{c,i}=\mathbf{R}_i\mathbf{X}_w+\mathbf{t}_i
\]

其中：

- \(\mathbf R_i\)：\(3\times3\) Rotation Matrix
- \(\mathbf t_i\)：\(3\times1\) Translation

COLMAP 的 `images.bin` 中保存的 pose 本质上用于描述这种 world → camera 变换。

---

## 2.3 图像坐标 Pixel Coordinate

最终显示在图片上的像素：

\[
\mathbf{x}=
\begin{bmatrix}
u\\v
\end{bmatrix}
\]

所以完整链路是：

\[
\boxed{
\mathbf X_w
\rightarrow
\mathbf X_c
\rightarrow
\text{normalized image plane}
\rightarrow
\text{distortion}
\rightarrow
(u,v)
}
\]

---

## 2.4 为什么要使用齐次坐标

三维点写成：

\[
\tilde{\mathbf X}=
\begin{bmatrix}
X\\Y\\Z\\1
\end{bmatrix}
\]

二维像素写成：

\[
\tilde{\mathbf x}=
\begin{bmatrix}
u\\v\\1
\end{bmatrix}
\]

好处是：

> Rotation、Translation、Projection 可以统一写成矩阵乘法。

最常见形式：

\[
\boxed{
\lambda\tilde{\mathbf x}
=
\mathbf K
[\mathbf R|\mathbf t]
\tilde{\mathbf X}
}
\]

这是多视图几何里最重要的公式之一。

---

# 3. 针孔相机模型：3D 为什么会投影成 2D

## 3.1 从相似三角形推导

相机坐标中一点：

\[
P=(X,Y,Z)
\]

成像平面距离光心为焦距 \(f\)。

由相似三角形：

\[
\frac{x}{f}=\frac{X}{Z}
\]

所以：

\[
x=f\frac{X}{Z}
\]

同理：

\[
y=f\frac{Y}{Z}
\]

这解释了透视现象：

- \(Z\) 越大，投影越小；
- 同样大小的物体越远看起来越小。

---

## 3.2 Normalized Image Coordinate

在先不考虑像素尺寸和主点时：

\[
x_n=\frac{X}{Z}
\]

\[
y_n=\frac{Y}{Z}
\]

这叫 normalized image plane。

之后再乘焦距并加 principal point。

---

# 4. Camera Intrinsics：相机自身的成像参数

一般针孔模型：

\[
\mathbf K=
\begin{bmatrix}
f_x&0&c_x\\
0&f_y&c_y\\
0&0&1
\end{bmatrix}
\]

其中：

- \(f_x,f_y\)：像素单位焦距
- \(c_x,c_y\)：Principal Point

于是：

\[
\lambda
\begin{bmatrix}
u\\v\\1
\end{bmatrix}
=
\mathbf K
\begin{bmatrix}
X_c\\Y_c\\Z_c
\end{bmatrix}
\]

展开：

\[
u=f_x\frac{X_c}{Z_c}+c_x
\]

\[
v=f_y\frac{Y_c}{Z_c}+c_y
\]

---

# 5. Videoto3D 当前为什么使用 SIMPLE_RADIAL

当前 `pipeline/colmap.py` 给 COLMAP 设置：

```text
ImageReader.single_camera = 1
ImageReader.camera_model = SIMPLE_RADIAL
```

同一段视频通常来自同一台相机，因此让所有 Frame 共享一套 Intrinsics 是合理的初始假设。

`SIMPLE_RADIAL` 参数：

\[
(f,c_x,c_y,k)
\]

## 5.1 Radial Distortion

归一化坐标：

\[
x=\frac{X_c}{Z_c},\qquad
y=\frac{Y_c}{Z_c}
\]

定义：

\[
r^2=x^2+y^2
\]

一阶径向畸变：

\[
x_d=x(1+kr^2)
\]

\[
y_d=y(1+kr^2)
\]

最终像素：

\[
u=f x_d+c_x
\]

\[
v=f y_d+c_y
\]

所以：

\[
\boxed{
u=f\frac{X_c}{Z_c}
\left(
1+k\left[
\left(\frac{X_c}{Z_c}\right)^2+
\left(\frac{Y_c}{Z_c}\right)^2
\right]
\right)+c_x
}
\]

\(v\) 同理。

## 5.2 为什么需要畸变模型

真实镜头不是理想针孔。

如果忽略明显畸变：

```text
同一个真实 3D 点
↓
模型预测像素位置
≠
真实检测到的像素位置
```

BA 会被迫用错误 Camera Pose / 3D Point 去补偿镜头误差。

结果可能：

- 焦距异常；
- Camera 轨迹扭曲；
- 3D 几何弯曲；
- Reprojection Error 增大。

---

# 6. 视频抽帧：为什么默认 4 FPS

当前实现：

```text
FFmpeg
-vf fps=4
-q:v 2
```

## 6.1 这是一个信息密度问题

假设视频：

\[
30\text{ FPS}
\]

但相机运动较慢，那么连续两帧：

```text
Frame 100
Frame 101
```

可能几乎一模一样。

全部保留会：

- Feature Extraction 重复；
- Matching 数量增加；
- 数据量变大；
- 收益有限。

抽太少则会：

- 相邻 Viewpoint Baseline 太大；
- Feature Correspondence 下降；
- Camera Registration 失败。

因此需要平衡：

\[
\text{Temporal Redundancy}
\quad\leftrightarrow\quad
\text{Viewpoint Continuity}
\]

---

## 6.2 拍摄速度和抽帧率的关系

设相机角速度：

\[
\omega\;(\text{degree/s})
\]

抽帧率：

\[
f_s\;(\text{frame/s})
\]

相邻抽帧的平均角度变化约：

\[
\Delta\theta \approx \frac{\omega}{f_s}
\]

如果你绕物体拍得非常快：

\[
\omega\uparrow
\]

就应该：

\[
f_s\uparrow
\]

否则相邻帧变化太大。

---

## 6.3 Artifact Inspector 看什么

```text
Frames
```

检查：

- 第一帧是否清晰；
- 中间是否运动模糊；
- 是否围绕目标覆盖充分；
- 是否大量重复；
- 最后是否完成完整角度覆盖。

---

# 7. SAM2：它解决的是“语义主体约束”，不是 Camera Geometry

SAM2 是 Promptable Video Segmentation 模型。

Videoto3D 当前：

```text
第一帧 Bounding Box
↓
SAM2 Video Predictor
↓
propagate_in_video
↓
每帧 Mask
```

并使用：

```text
CUDA
bfloat16 autocast
video/state CPU offload
```

来运行。

---

## 7.1 Mask 数学表示

每帧：

\[
M_i(u,v)\in\{0,1\}
\]

SAM2 内部输出的是 Mask Logit。

当前 worker 用：

\[
M_i(u,v)=
\mathbf 1[
L_i(u,v)>0
]
\]

保存为 8-bit PNG：

```text
0   → background
255 → foreground
```

---

## 7.2 为什么 Overlay 很重要

只有数量：

```text
80 masks / 80 frames
```

并不能说明 Mask 正确。

可能发生：

```text
数量完整
但第 40 帧以后开始追踪到桌面
```

所以必须看：

\[
I_i^\text{overlay}
=
(1-\alpha)I_i+
\alpha\,\text{Color}(M_i)
\]

这就是 GUI 中 Original / Mask / Overlay 的意义。

---

## 7.3 为什么不直接把背景像素设成黑色再跑 COLMAP

假设目标是光滑陶瓷娃娃。

目标表面：

```text
白色
平滑
纹理少
```

背景可能：

```text
桌面纹理
墙角
书本
地板
```

这些背景 Feature 虽然不是最终目标，却非常有利于估计 Camera Motion。

如果只保留目标：

\[
N_\text{features}\downarrow
\]

可能导致：

\[
N_\text{matches}\downarrow
\]

进而：

\[
\text{Pose Robustness}\downarrow
\]

因此 Videoto3D 选择：

\[
\boxed{
\text{RGB for Geometry}
+
\text{Mask for Object Constraint}
}
\]

---

# 8. Feature Extraction：计算机如何找到“可重复识别的局部点”

COLMAP 不是直接识别：

```text
这是眼睛
这是鼻子
```

它寻找局部视觉结构。

每个 Feature 通常包含：

\[
(\mathbf p,\mathbf d)
\]

其中：

- \(\mathbf p=(u,v,\ldots)\)：Keypoint
- \(\mathbf d\)：Descriptor

Descriptor 的目标不是描述“物体类别”，而是：

> 当同一个真实局部区域出现在另一张图里时，两者 Descriptor 应该足够相似。

---

## 8.1 为什么角点比纯色区域好

纯色墙面：

```text
← 往左移动一点
看起来还是一样
```

所以位置不容易唯一确定。

角点：

```text
水平边缘 + 垂直边缘同时存在
```

平移以后局部模式变化明显，因此更容易定位。

从图像梯度角度：

\[
\nabla I=
\begin{bmatrix}
I_x\\I_y
\end{bmatrix}
\]

如果局部只有单方向梯度，就存在 aperture ambiguity。

如果多个方向都有明显变化，局部位置更稳定。

---

# 9. Feature Matching：找到跨帧 Correspondence

两张图：

\[
I_i,\quad I_j
\]

Feature 集合：

\[
D_i=\{\mathbf d_{i1},\ldots\}
\]

\[
D_j=\{\mathbf d_{j1},\ldots\}
\]

通过 Descriptor Distance 找候选：

\[
j^*
=
\arg\min_j
\|\mathbf d_i-\mathbf d_j\|
\]

得到：

\[
\mathbf x_i
\leftrightarrow
\mathbf x_j
\]

---

## 9.1 Videoto3D 为什么使用 Sequential Matcher

视频天然有时间顺序。

当前 COLMAP 参数包括：

```text
SequentialMatching.overlap = 10
SequentialMatching.quadratic_overlap = 1
```

基本思想：

> Frame 30 最可能与 Frame 29、31、附近若干帧存在大量共同可见区域。

相比所有图两两匹配：

\[
O(N^2)
\]

Sequential Matching 更符合视频输入结构，也能减少无意义 Pair。

---

# 10. Epipolar Geometry：匹配为什么不能随便连

假设一个 3D Point \(X\) 在 Camera 1 中投影为 \(x_1\)。

仅凭 \(x_1\)，它在三维空间中不是一个点，而是一条 Ray：

```text
Camera 1
   \
    \
     \  X 可能在这条线上任意深度
```

这个 Ray 投影到 Camera 2 图像中形成一条：

> Epipolar Line

因此正确匹配 \(x_2\) 必须落在这条线附近。

---

## 10.1 Essential Matrix 推导

归一化相机坐标中：

\[
\mathbf x_1,\mathbf x_2
\]

两相机关系：

\[
\mathbf X_2
=
\mathbf R\mathbf X_1+\mathbf t
\]

几何上：

\[
\mathbf x_2,\mathbf t,\mathbf R\mathbf x_1
\]

共面。

三个向量共面的标量三重积为 0：

\[
\mathbf x_2^\top
(
\mathbf t\times
\mathbf R\mathbf x_1
)=0
\]

叉乘可以写成 skew-symmetric matrix：

\[
[\mathbf t]_\times
=
\begin{bmatrix}
0&-t_z&t_y\\
t_z&0&-t_x\\
-t_y&t_x&0
\end{bmatrix}
\]

于是：

\[
\mathbf x_2^\top
[\mathbf t]_\times
\mathbf R
\mathbf x_1
=0
\]

定义：

\[
\boxed{
\mathbf E
=
[\mathbf t]_\times\mathbf R
}
\]

得到：

\[
\boxed{
\mathbf x_2^\top
\mathbf E
\mathbf x_1=0
}
\]

这就是 Essential Constraint。

---

## 10.2 Fundamental Matrix

真实图像像素：

\[
\tilde{\mathbf u}_1=\mathbf K_1\mathbf x_1
\]

\[
\tilde{\mathbf u}_2=\mathbf K_2\mathbf x_2
\]

代入：

\[
\mathbf x_1=\mathbf K_1^{-1}\tilde{\mathbf u}_1
\]

\[
\mathbf x_2=\mathbf K_2^{-1}\tilde{\mathbf u}_2
\]

因此：

\[
\tilde{\mathbf u}_2^\top
\mathbf K_2^{-\top}
\mathbf E
\mathbf K_1^{-1}
\tilde{\mathbf u}_1
=0
\]

定义：

\[
\boxed{
\mathbf F
=
\mathbf K_2^{-\top}
\mathbf E
\mathbf K_1^{-1}
}
\]

所以：

\[
\boxed{
\tilde{\mathbf u}_2^\top
\mathbf F
\tilde{\mathbf u}_1
=0
}
\]

---

# 11. RANSAC：为什么错误 Feature Match 不会直接毁掉模型

Descriptor Match 一定包含 Outlier。

假设：

```text
100 个候选 match
70 个正确
30 个错误
```

如果直接最小二乘拟合几何模型，Outlier 会严重污染结果。

RANSAC：

```text
随机取最小样本
↓
估计模型
↓
统计多少 Match 符合模型
↓
重复
↓
选择 Inlier 最多的模型
```

---

## 11.1 需要多少次随机采样

设：

- \(w\)：单个 Match 是 Inlier 的概率
- \(s\)：一次模型估计需要的最小样本数
- \(p\)：希望至少有一次“全 Inlier Sample”的成功概率

一次采样全正确：

\[
w^s
\]

一次失败：

\[
1-w^s
\]

连续 \(N\) 次都失败：

\[
(1-w^s)^N
\]

希望：

\[
1-(1-w^s)^N\ge p
\]

得到：

\[
\boxed{
N
\ge
\frac{\log(1-p)}
{\log(1-w^s)}
}
\]

这解释了：

> Outlier 越多，RANSAC 需要尝试越多次。

---

# 12. SfM：为什么能同时恢复 Camera 和 3D

SfM 要同时求两个未知集合：

\[
\{\mathbf R_i,\mathbf t_i,\mathbf K_i\}
\]

以及：

\[
\{\mathbf X_j\}
\]

观测则是：

\[
\mathbf x_{ij}
\]

表示 Point \(j\) 在 Image \(i\) 中的像素。

形成一个大型优化问题：

```text
Camera parameters
       ↘
        Projection → observed pixels
       ↗
3D points
```

---

# 13. Incremental SfM：COLMAP 当前 Mapper 的基本逻辑

Videoto3D 使用：

```text
colmap mapper
Mapper.multiple_models = 0
```

属于 Incremental Reconstruction。

概念流程：

```text
选择一个可靠 Image Pair
↓
估计两相机相对 Pose
↓
Triangulate 初始 3D Points
↓
找下一张有足够 2D-3D 对应的 Image
↓
PnP 求新 Camera Pose
↓
Triangulate 新 Points
↓
Local / Global Bundle Adjustment
↓
循环
```

---

# 14. Triangulation：两个像素如何恢复 3D 点

设：

\[
\mathbf P_1=\mathbf K_1[\mathbf R_1|\mathbf t_1]
\]

\[
\mathbf P_2=\mathbf K_2[\mathbf R_2|\mathbf t_2]
\]

同一个 3D Point：

\[
\tilde{\mathbf X}
\]

投影：

\[
\lambda_1\tilde{\mathbf x}_1=
\mathbf P_1\tilde{\mathbf X}
\]

\[
\lambda_2\tilde{\mathbf x}_2=
\mathbf P_2\tilde{\mathbf X}
\]

---

## 14.1 消掉未知尺度 \(\lambda\)

因为两个齐次向量平行：

\[
\tilde{\mathbf x}\times
(\mathbf P\tilde{\mathbf X})
=0
\]

令：

\[
\tilde{\mathbf x}=
\begin{bmatrix}
u\\v\\1
\end{bmatrix}
\]

\(\mathbf P\) 的三行记作：

\[
\mathbf p_1^\top,\mathbf p_2^\top,\mathbf p_3^\top
\]

可以得到两条独立线性方程：

\[
(u\mathbf p_3^\top-\mathbf p_1^\top)\tilde{\mathbf X}=0
\]

\[
(v\mathbf p_3^\top-\mathbf p_2^\top)\tilde{\mathbf X}=0
\]

两张图组合：

\[
\mathbf A\tilde{\mathbf X}=0
\]

通过 SVD 求：

\[
\tilde{\mathbf X}
\]

这就是常见 DLT Triangulation 的核心。

---

## 14.2 为什么两台 Camera 太接近不好

如果两条 Viewing Ray 几乎平行：

```text
\      \
 \      \
  \      \
```

它们交会位置对像素误差极其敏感。

Baseline 越合理，几何条件通常越好。

因此拍视频不能：

```text
只站在一个位置原地旋转手机
```

需要真正发生 Translation / Orbit。

---

# 15. PnP：已经有 3D Point 时，如何定位新相机

假设已经存在一组：

\[
\mathbf X_j
\]

新图片中又匹配到：

\[
\mathbf x_j
\]

要找：

\[
\mathbf R,\mathbf t
\]

满足：

\[
\mathbf x_j
\approx
\pi(
\mathbf K,
\mathbf R,
\mathbf t,
\mathbf X_j
)
\]

这就是 Perspective-n-Point。

SfM 中：

```text
已有 3D Map
+
新 Image 的 2D Feature
↓
2D-3D Correspondence
↓
PnP + RANSAC
↓
新 Camera Pose
```

这就是“注册一张新图片”的核心思想。

---

# 16. Reprojection Error：整个几何链的统一体检指标

真实检测像素：

\[
\mathbf x_{ij}
\]

当前模型预测：

\[
\hat{\mathbf x}_{ij}
=
\pi(
\mathbf K_i,
\mathbf R_i,
\mathbf t_i,
\mathbf X_j
)
\]

Residual：

\[
\mathbf r_{ij}
=
\mathbf x_{ij}
-
\hat{\mathbf x}_{ij}
\]

Reprojection Error：

\[
e_{ij}
=
\|\mathbf r_{ij}\|_2
\]

即：

\[
\boxed{
e_{ij}
=
\sqrt{
(u-\hat u)^2+
(v-\hat v)^2
}
}
\]

单位：

```text
pixel
```

---

## 16.1 它为什么这么重要

一个 3D Point 本身“看起来合理”不够。

真正的问题是：

> 把这个 3D Point 按 Camera Model 投影回原始照片，它能不能回到 Feature 实际出现的位置？

如果能：

```text
Camera
+
Intrinsics
+
3D Point
```

三者互相一致。

---

# 17. Bundle Adjustment：SfM 最重要的优化

BA 同时调整：

```text
Camera Pose
Camera Intrinsics
3D Points
```

使所有 Reprojection Residual 尽量小。

最基本目标：

\[
\boxed{
\min_{\Theta,\{\mathbf X_j\}}
\sum_{(i,j)\in\mathcal O}
\left\|
\mathbf x_{ij}
-
\pi(
\Theta_i,\mathbf X_j
)
\right\|_2^2
}
\]

其中：

- \(\Theta_i\)：第 \(i\) 个 Camera 参数
- \(\mathcal O\)：所有有效观测

实际系统通常会使用 robust loss 减少 Outlier 影响：

\[
\min
\sum
\rho(
\|\mathbf r_{ij}\|^2
)
\]

---

## 17.1 为什么必须“联合”优化

如果只固定 Camera 优化 Point：

```text
Camera 初始误差
会被 Point 被迫吸收
```

如果只固定 Point 优化 Camera：

```text
Point 初始误差
会被 Camera 被迫吸收
```

联合优化才能让误差在整个几何系统里重新分配。

---

# 18. Scale Ambiguity：单目 SfM 为什么没有绝对尺寸

如果所有 Camera Translation 和所有 3D Points 同时乘：

\[
s>0
\]

即：

\[
\mathbf t_i' = s\mathbf t_i
\]

\[
\mathbf X_j'=s\mathbf X_j
\]

投影中的：

\[
X/Z,\quad Y/Z
\]

不会改变。

因此图像无法区分：

```text
10 cm 的小物体
和
按相同比例放大的 1 m 物体
```

只凭单目多视图，通常恢复的是：

> **up-to-scale geometry**

如果要真实毫米尺寸，需要额外尺度信息：

- 已知长度；
- 标定板；
- 深度传感器；
- 已知 Camera Baseline；
- 其他外部尺度约束。

---

# 19. COLMAP Sparse Point Cloud 中每个 Point 还包含什么

不仅有：

\[
(X,Y,Z)
\]

还包含：

```text
RGB
Reprojection Error
Track
```

Track 表示：

> 这个 3D Point 被哪些 Image / Keypoint 观察到。

Track Length：

\[
L_j=
|\text{observations of point }j|
\]

较大的 Track 通常意味着：

```text
同一个 3D Point
被更多视角共同确认
```

因此 Mean Track Length 是很有价值的几何质量信息。

---

# 20. Registered Images：比“总帧数”更重要

输入：

\[
N
\]

成功估计 Pose 的 Frame：

\[
N_r
\]

Registration Ratio：

\[
\boxed{
R_\text{reg}
=
\frac{N_r}{N}
}
\]

例如：

\[
\frac{114}{120}=95\%
\]

未注册图片意味着：

```text
这张图无法可靠加入当前 3D 模型
```

可能因为：

- 模糊；
- Feature 太少；
- 视角跳跃；
- 反光；
- 曝光变化；
- 重复纹理；
- 相机运动过大。

---

# 21. 为什么 Sparse 正确以后才值得继续

如果 Camera Pose 已经错：

```text
错误 Camera
↓
错误射线方向
↓
Dense Stereo 无法正确找深度
↓
Texture 投影错位
↓
Gaussian 训练监督也矛盾
```

因此排错永远应该：

\[
\boxed{
\text{先检查 Camera / Sparse，再检查最终资产}
}
\]

---

# 22. COLMAP Undistort：为什么 Mesh Route 还要再处理图像

Shared COLMAP 可以处理带畸变 Camera Model。

但 OpenMVS 希望输入更标准化的相机/图像几何。

Undistort 的任务：

```text
原始畸变 Image
+
COLMAP Intrinsics
↓
去畸变 Image
+
对应的新 Camera Model
```

从数学上是在求原始 distorted pixel：

\[
(u_d,v_d)
\]

对应的 undistorted ray：

\[
(x,y)
\]

再把它重新采样到一个规则针孔图像中。

---

## 22.1 Max Image Size

当前默认：

```text
2000
```

如果原图长边更大，会限制进入 OpenMVS 的分辨率。

这影响：

\[
\text{Detail}
\quad\leftrightarrow\quad
\text{Compute / Memory}
\]

---

# 23. InterfaceCOLMAP：只是格式桥接吗？

基本上是。

它把：

```text
COLMAP Camera + Image + Sparse
```

转换成 OpenMVS Scene 格式：

```text
scene.mvs
```

这里的重点不是“重新计算 3D”，而是：

> 把两套软件对 Camera、Image、Point Cloud 的表示统一起来。

---

# 24. MVS：为什么知道 Camera Pose 后可以恢复 Dense Surface

SfM 只找 Feature。

MVS 的目标是：

> 对更多像素估计深度。

对于 Reference Image 中某一个 Pixel：

\[
\mathbf x_r
\]

给定一个候选 Depth：

\[
d
\]

可以反投影成 3D：

\[
\mathbf X(d)
=
\mathbf R_r^\top
\left(
d\mathbf K_r^{-1}\tilde{\mathbf x}_r
-
\mathbf t_r
\right)
\]

然后投影到 Neighbor Camera：

\[
\hat{\mathbf x}_n(d)
=
\pi_n(\mathbf X(d))
\]

如果 \(d\) 正确，那么 Reference 与 Neighbor 中对应 Patch 应该外观一致。

于是定义 Photometric Cost：

\[
C(d)
=
D(
P_r(\mathbf x_r),
P_n(\hat{\mathbf x}_n(d))
)
\]

理想深度：

\[
\boxed{
d^*
=
\arg\min_d C(d)
}
\]

---

# 25. Stereo 的经典深度公式

平行双目简化模型：

- Baseline：\(B\)
- Focal：\(f\)
- 左右像素水平差：Disparity \(d\)

得到：

\[
\boxed{
Z=\frac{fB}{d}
}
\]

这条公式非常值得记住。

它告诉我们：

### Baseline 太小

\[
B\downarrow
\Rightarrow
d\downarrow
\]

Disparity 太小，深度对像素误差敏感。

### 物体越远

\[
Z\uparrow
\Rightarrow
d\downarrow
\]

同样更难估深度。

---

## 25.1 深度误差近似

由：

\[
Z=\frac{fB}{d}
\]

对 \(d\) 求导：

\[
\frac{\partial Z}{\partial d}
=
-\frac{fB}{d^2}
\]

利用：

\[
d=\frac{fB}{Z}
\]

代入：

\[
\left|
\frac{\partial Z}{\partial d}
\right|
=
\frac{Z^2}{fB}
\]

所以小 disparity error \(\delta d\) 导致：

\[
\boxed{
\delta Z
\approx
\frac{Z^2}{fB}\delta d
}
\]

结论：

- 更远的物体，深度误差近似按 \(Z^2\) 增长；
- 合理 Baseline 很重要；
- 更大 Focal / 更高有效像素精度能改善深度。

---

# 26. OpenMVS DensifyPointCloud

OpenMVS 的定位是：

```text
Camera Poses + Sparse Point Cloud
↓
Dense Point Cloud
```

Videoto3D Artifact Inspector 中：

```text
COLMAP Sparse
→ Dense Cloud
```

就是最直观的 MVS 教学画面。

---

## 26.1 Resolution Level

概念上：

```text
level 0 → 最高/基础分辨率
level 1 → 更低一层
level 2 → 再低
```

更高图像分辨率通常意味着：

```text
更多细节
更多 Pixel
更高计算量
更高内存需求
```

---

# 27. Depth Fusion：为什么不是每张图的 Depth Map 直接拼起来

每一个 Reference Image 都可能估出自己的深度。

同一个真实表面点可能被多个 View 估计。

需要检查：

```text
几何一致性
可见性
深度相容性
法向相容性
置信度
```

然后融合。

最终 Dense Point：

\[
\mathbf X_k
\]

通常来自多个视图的共同支持，而不是某一张图单独决定。

---

# 28. Dense Point Cloud 和 Mesh 的本质区别

Point Cloud：

\[
\mathcal P=
\{\mathbf X_1,\mathbf X_2,\ldots,\mathbf X_N\}
\]

只回答：

```text
这里有表面采样点
```

没有明确回答：

```text
哪三个点组成一个表面三角形？
哪里是连续表面？
哪里应该是洞？
```

Mesh：

\[
\mathcal M=(V,F)
\]

其中：

\[
V=\{\mathbf v_i\}
\]

\[
F=\{(i,j,k)\}
\]

Face 指定三个 Vertex 构成 Triangle。

---

# 29. Mesh Reconstruction：从点估计连续表面

从数学上，这是一个 Surface Reconstruction 问题。

我们希望寻找表面：

\[
S
\]

使其：

1. 靠近 Dense Point Cloud；
2. 与 Camera Visibility 一致；
3. 尽量形成合理连续表面；
4. 不产生大量无意义内部表面。

可以概念化为：

\[
\boxed{
S^*
=
\arg\min_S
E_\text{data}(S,\mathcal P)
+
\lambda E_\text{regularization}(S)
}
\]

注意：

> 这只是理解 Surface Reconstruction 的统一能量形式，不是在宣称 OpenMVS 当前版本内部恰好只使用这一条简单公式。

---

# 30. Triangle Normal

三角形：

\[
(\mathbf v_0,\mathbf v_1,\mathbf v_2)
\]

两个 Edge：

\[
\mathbf e_1=\mathbf v_1-\mathbf v_0
\]

\[
\mathbf e_2=\mathbf v_2-\mathbf v_0
\]

Face Normal：

\[
\boxed{
\mathbf n
=
\frac{
\mathbf e_1\times\mathbf e_2
}{
\|\mathbf e_1\times\mathbf e_2\|
}
}
\]

Normal 影响：

- 光照；
- Front / Back Face；
- Surface Orientation；
- Refinement。

---

# 31. Mesh Refinement：为什么 Raw Mesh 以后还需要优化

Raw Mesh 已经有拓扑，但表面可能：

```text
过粗
局部位置偏移
小细节损失
三角形不规则
```

Refinement 可以概念理解为：

\[
E(V)
=
E_\text{photo}(V)
+
\lambda_s E_\text{smooth}(V)
+
\lambda_r E_\text{regularize}(V)
\]

其中：

- \(V\)：Vertex Position
- Photometric Term：不同 Camera 看到的 Mesh 投影应与图像一致
- Smooth / Regularization：避免过度噪声和畸形面

最终：

\[
V^*
=
\arg\min_V E(V)
\]

Artifact Inspector 的：

```text
Raw Mesh ↔ Refined Mesh
```

就是观察这个优化有没有实际改善。

---

# 32. Texture Mapping：几何和颜色为什么是两件事

Mesh 只有：

```text
Vertex
Face
Normal
```

并不知道陶瓷娃娃衣服是什么颜色。

Texture Mapping 要建立：

\[
\text{3D Surface Point}
\leftrightarrow
\text{2D Texture Coordinate}
\]

---

# 33. UV Coordinate

每个 Mesh Vertex 可以附加：

\[
(u,v)
\]

通常：

\[
u,v\in[0,1]
\]

表示 Texture Image 上的位置。

Triangle 的三个 Vertex：

\[
(u_0,v_0),
(u_1,v_1),
(u_2,v_2)
\]

三角形内部点通过 Barycentric Coordinate：

\[
\mathbf p
=
\alpha\mathbf v_0+
\beta\mathbf v_1+
\gamma\mathbf v_2
\]

其中：

\[
\alpha+\beta+\gamma=1
\]

Texture Coordinate 同样插值：

\[
\boxed{
\mathbf t
=
\alpha\mathbf t_0+
\beta\mathbf t_1+
\gamma\mathbf t_2
}
\]

---

# 34. Texture Atlas

为了把复杂 Mesh Surface 展开到二维图像，会切成多个 UV Island：

```text
3D Surface
↓ unwrap
2D Islands
↓ pack
Texture Atlas
```

Artifact Inspector 的 Texture Atlas 很有教学意义：

> 它不是“原始照片”，而是重排后用于给 Mesh 着色的二维表面贴图。

---

# 35. 为什么多相机 Texture 会有 Seam

不同 View 可能存在：

```text
曝光不同
白平衡不同
反射变化
遮挡
视角变化
重建误差
```

同一 Surface Region 从 Camera A 和 Camera B 采样的颜色可能不同。

于是 Patch 接缝处出现：

```text
Seam
```

Seam Leveling 的目标是减少这种不连续。

Videoto3D 当前对 OpenMVS 2.4.0 保持：

```text
global seam leveling = 0
local seam leveling  = 0
```

这是项目针对已遇到纹理黑块问题采用的工程 workaround，并不是说 Seam Leveling 理论上没有价值。

---

# 36. Blender → GLB：为什么最终不是继续保留 OBJ

OBJ 通常：

```text
model.obj
model.mtl
texture.png / jpg
```

多个文件必须一起管理。

GLB 是 glTF 的 binary container，可以把：

```text
Geometry
Material
Texture
Scene Graph
```

打包成单一文件。

因此：

```text
<run_id>.glb
```

更适合：

- GitHub Demo 截图来源；
- Three.js；
- 个人网站；
- 单文件分发。

---

# 37. 现在切换到 Splat Route：为什么不一定需要 Mesh

Mesh 假设：

> 场景最核心的表示是一个明确的二维表面。

Gaussian Splat 更接近：

> 用大量可投影的三维椭球 Primitive 直接解释多视角图像。

因此对：

```text
毛发
毛绒
细小边缘
半透明视觉
复杂 View-dependent Appearance
```

可能有更好的视觉表现。

---

# 38. 3D Gaussian 的数学形式

一个 Gaussian 有 Center：

\[
\boldsymbol\mu
=
\begin{bmatrix}
\mu_x\\\mu_y\\\mu_z
\end{bmatrix}
\]

Covariance：

\[
\boldsymbol\Sigma
\in\mathbb R^{3\times3}
\]

三维 Gaussian：

\[
\boxed{
G(\mathbf x)
=
\exp
\left(
-\frac12
(\mathbf x-\boldsymbol\mu)^\top
\boldsymbol\Sigma^{-1}
(\mathbf x-\boldsymbol\mu)
\right)
}
\]

---

# 39. 为什么是椭球而不是普通球

如果：

\[
\boldsymbol\Sigma
=
\sigma^2\mathbf I
\]

则各方向尺度相同，是 Isotropic Gaussian。

3DGS 通常允许 Anisotropic：

```text
x / y / z 方向尺度不同
并允许旋转
```

可以更好贴合：

```text
平面
细长结构
斜面
边缘
```

---

# 40. Scale + Rotation 如何变成 Covariance

令：

\[
\mathbf S=
\begin{bmatrix}
s_x&0&0\\
0&s_y&0\\
0&0&s_z
\end{bmatrix}
\]

Rotation：

\[
\mathbf R
\]

常见构造：

\[
\boxed{
\boldsymbol\Sigma
=
\mathbf R
\mathbf S
\mathbf S^\top
\mathbf R^\top
}
\]

由于：

\[
\mathbf S\mathbf S^\top
=
\operatorname{diag}
(s_x^2,s_y^2,s_z^2)
\]

因此：

- \(s_x,s_y,s_z\) 控制椭球轴长；
- \(R\) 控制方向。

实际 PLY 中常把 Rotation 存成 Quaternion。

---

# 41. Quaternion 简要理解

Quaternion：

\[
q=(w,x,y,z)
\]

单位 Quaternion：

\[
w^2+x^2+y^2+z^2=1
\]

可以转成 Rotation Matrix。

相比 Euler Angle：

```text
不会直接遭遇同样形式的 gimbal-lock 表达问题
插值方便
优化连续性更好
```

所以很多 3DGS 实现用 Quaternion 表达 Gaussian Orientation。

---

# 42. 3D Gaussian 如何投影到屏幕

Gaussian Center 先像普通 3D Point 一样：

\[
\boldsymbol\mu_c
=
\mathbf R_c\boldsymbol\mu+\mathbf t_c
\]

再投影：

\[
\mathbf p
=
\pi(\boldsymbol\mu_c)
\]

但是只投影 Center 不够。

我们还要把 3D Covariance 投影成 2D Ellipse。

---

## 42.1 Perspective Projection Jacobian

简化针孔：

\[
u=f_x\frac{X}{Z}+c_x
\]

\[
v=f_y\frac{Y}{Z}+c_y
\]

对：

\[
(X,Y,Z)
\]

求 Jacobian：

\[
\mathbf J=
\begin{bmatrix}
\frac{\partial u}{\partial X}
&
\frac{\partial u}{\partial Y}
&
\frac{\partial u}{\partial Z}
\\
\frac{\partial v}{\partial X}
&
\frac{\partial v}{\partial Y}
&
\frac{\partial v}{\partial Z}
\end{bmatrix}
\]

得到：

\[
\boxed{
\mathbf J=
\begin{bmatrix}
\frac{f_x}{Z}
&
0
&
-\frac{f_xX}{Z^2}
\\
0
&
\frac{f_y}{Z}
&
-\frac{f_yY}{Z^2}
\end{bmatrix}
}
\]

---

## 42.2 3D Covariance → 2D Covariance

如果 World Gaussian Covariance 为：

\[
\Sigma_w
\]

先经过 Camera Rotation：

\[
\Sigma_c
=
R_c\Sigma_wR_c^\top
\]

局部线性化投影：

\[
\boxed{
\Sigma_{2D}
\approx
J\Sigma_cJ^\top
}
\]

所以屏幕上不是一个点，而是一个二维椭圆 footprint。

这就是“splat”的几何基础。

---

# 43. Alpha Compositing：很多 Gaussian 如何叠成一个 Pixel

假设沿 Camera Ray，Gaussian 按深度排序：

\[
1,2,\ldots,N
\]

每个贡献：

- Color \(c_i\)
- Alpha \(\alpha_i\)

第 \(i\) 个 Gaussian 前面的透射率：

\[
\boxed{
T_i
=
\prod_{j<i}
(1-\alpha_j)
}
\]

最终 Pixel Color：

\[
\boxed{
C
=
\sum_{i=1}^{N}
T_i\alpha_i c_i
}
\]

这就是 Front-to-Back Alpha Compositing。

---

## 43.1 为什么 Opacity 很重要

如果某 Gaussian：

\[
\alpha\approx0
\]

几乎看不见。

如果：

\[
\alpha\approx1
\]

会强烈遮挡后面的 Gaussian。

训练时调整 Opacity 就是在学习：

> 哪些 Primitive 应该真正贡献表面颜色。

---

# 44. Spherical Harmonics：为什么 Gaussian 颜色可以随观察方向改变

简单 RGB：

\[
c=\text{constant}
\]

意味着从任何方向看颜色完全相同。

但现实有：

```text
高光
反射
View-dependent Appearance
```

因此 3DGS 常使用 Spherical Harmonics：

\[
\boxed{
c(\mathbf d)
=
\sum_{l=0}^{L}
\sum_{m=-l}^{l}
c_{lm}
Y_{lm}(\mathbf d)
}
\]

其中：

- \(\mathbf d\)：View Direction
- \(Y_{lm}\)：SH Basis
- \(c_{lm}\)：可学习系数

低阶 SH 就能表达一定的方向颜色变化。

---

# 45. Gaussian Splat Training 在优化什么

目标是：

\[
\text{Render}(Camera_i,\mathcal G)
\approx
I_i
\]

其中：

\[
\mathcal G
=
\{G_1,\ldots,G_N\}
\]

可以概念化写成：

\[
\boxed{
\min_{\mathcal G}
\sum_i
\mathcal L(
\hat I_i,I_i
)
}
\]

可优化参数可能包括：

```text
Position
Scale
Rotation
Opacity
Color / SH
```

Gaussian 数量本身也可能通过：

```text
grow
split
clone
prune
MCMC-like relocation
```

发生变化。

Brush 的内部训练策略会随版本演进；Videoto3D 不应把某一历史版 3DGS 论文的所有内部细节误认为 Brush 永远固定不变。

---

# 46. 为什么 COLMAP Sparse 是 Gaussian 很好的初始化

完全随机在 3D 空间放 Gaussian：

```text
搜索空间巨大
训练不稳定
```

COLMAP Sparse Points 已经告诉我们：

```text
真实表面大概在哪里
```

所以可以初始化：

\[
\mu_i
\approx
\mathbf X_i^\text{sparse}
\]

这就是经典 3DGS 从 SfM Sparse 初始化的直觉。

---

# 47. Videoto3D 为什么还要做 Object-only Sparse

Shared Sparse 包含：

```text
目标
+
桌面
+
墙面
+
环境
```

如果全部送给 Brush 初始化：

```text
背景也会大量获得初始 Gaussian
```

所以 Videoto3D 对每个 Sparse Point 的 Track 做 Mask 投票。

---

# 48. Object Sparse 的多视角投票数学

某 3D Sparse Point：

\[
\mathbf X_j
\]

它被 \(n_j\) 个 Image 观察。

对于每个 Observation，COLMAP 已经保存 Point 对应的 2D Feature：

\[
\mathbf x_{ij}
\]

查询 Mask：

\[
m_{ij}
=
M_i(\mathbf x_{ij})
\in\{0,1\}
\]

有效前景数：

\[
F_j
=
\sum_i m_{ij}
\]

Foreground Ratio：

\[
\boxed{
r_j
=
\frac{F_j}{V_j}
}
\]

其中 \(V_j\) 是有效 Mask Observation 数。

当前默认规则：

\[
F_j\ge2
\]

并且：

\[
r_j\ge0.60
\]

才保留初始化 Point。

---

## 48.1 为什么不是“只看一张 Mask”

一张图可能：

- Mask 边界错误；
- 遮挡；
- Point 刚好投影在边界；
- SAM2 局部漂移。

多视角投票：

\[
\text{single-view error}
\rightarrow
\text{multi-view consensus}
\]

更加稳健。

---

# 49. 为什么 Object Sparse 干净，Raw Splat 仍然可能重新长出背景

训练过程不是：

```text
固定 Sparse Points
只调整颜色
```

Gaussian 会移动、增长、分裂或重新分布。

监督图像仍然包含大量视觉信息。

所以训练后可能出现：

```text
halo
near-object background
floor / wall remnants
```

因此：

\[
\boxed{
\text{Clean Initialization}
\neq
\text{Guaranteed Clean Final Splat}
}
\]

这就是 V0.11 后增加 Post-Brush Cleanup 的原因。

---

# 50. Final Splat Cleanup：这是 Videoto3D 非常值得理解的一步

输入：

```text
Raw Gaussian PLY
COLMAP Camera Poses
Camera Intrinsics
SAM2 Masks
```

对于每个 Gaussian Center：

\[
\mathbf G_j=
(X_j,Y_j,Z_j)
\]

遍历已注册 Camera。

---

## 50.1 World → Camera

\[
\mathbf G_{c,ij}
=
R_i\mathbf G_j+t_i
\]

只有：

\[
Z_{c,ij}>0
\]

才在 Camera 前方。

---

## 50.2 Perspective Division

\[
x_{ij}
=
\frac{X_{c,ij}}{Z_{c,ij}}
\]

\[
y_{ij}
=
\frac{Y_{c,ij}}{Z_{c,ij}}
\]

---

## 50.3 再应用 Camera Distortion + Intrinsics

对于当前常见 SIMPLE_RADIAL：

\[
r^2=x^2+y^2
\]

\[
d=1+kr^2
\]

\[
u=f(xd)+c_x
\]

\[
v=f(yd)+c_y
\]

因此 Cleanup 与 Shared COLMAP 使用的是相同相机几何思想。

---

## 50.4 Mask Vote

如果投影像素在 Image Boundary 内：

\[
V_j\leftarrow V_j+1
\]

若：

\[
M_i(u,v)\ge128
\]

则：

\[
F_j\leftarrow F_j+1
\]

最终：

\[
\boxed{
r_j=
\frac{F_j}{V_j}
}
\]

当前默认保留条件：

\[
V_j\ge3
\]

且：

\[
r_j\ge0.70
\]

即：

\[
\boxed{
\text{keep}_j
=
[V_j\ge3]
\land
[r_j\ge0.70]
}
\]

---

# 51. Cleanup Threshold 怎么理解

假设一个 Gaussian 被 10 个 Camera 看见。

### Case A

\[
F=9,\quad V=10
\]

\[
r=0.9
\]

很可能属于主体。

### Case B

\[
F=2,\quad V=10
\]

\[
r=0.2
\]

很可能属于背景。

### Case C

\[
F=2,\quad V=2
\]

\[
r=1.0
\]

Ratio 看起来完美，但只有 2 个视角支持，证据不足。

所以同时需要：

```text
ratio threshold
+
minimum views
```

---

# 52. Cleanup 不是完整 Occlusion Reasoning

当前实现投影的是：

```text
Gaussian Center
```

并查询 SAM2 Mask。

它没有完整求：

```text
这个 Gaussian 是否被另一个前景表面遮挡
```

因此它是：

> 轻量级 Multi-view Semantic Consensus Filter

而不是完整 Visibility-aware 3D Segmentation。

理解这个边界很重要。

---

# 53. Raw / Clean Splat A/B 为什么是重要 Artifact

如果：

```text
Raw 很差
Clean 也差
```

问题可能更早：

```text
Camera
Object Sparse
Brush Training
Capture
```

如果：

```text
Raw 主体好但背景多
Clean 明显变好
```

说明 Cleanup 正常发挥作用。

如果：

```text
Raw 好
Clean 缺胳膊 / 缺边缘
```

说明：

```text
Mask
cleanup_ratio
cleanup_min_views
```

可能过严。

---

# 54. Quality Report：不要把所有数字都当“越大越好”

## 54.1 Registration Ratio

通常越高越好，但：

```text
100% 注册
不等于 Camera Pose 一定完全正确
```

---

## 54.2 Sparse Points

更多通常代表更丰富 Geometry Observation。

但：

```text
错误 Match 也可能产生错误点
```

所以不能只追求数量。

---

## 54.3 Reprojection Error

越低通常越好。

但如果模型过度拟合或 Camera Model 不合理，也不能单独只看 Error。

要组合：

```text
Camera trajectory
Registration
Track length
Point cloud shape
Reprojection error
```

---

## 54.4 Dense Points

不是越多越好。

极大量 Floating Noise：

```text
Dense Points ↑
质量反而 ↓
```

必须直接看 Dense Cloud。

---

## 54.5 Mesh Vertices / Faces

面数是复杂度，不是质量。

同一个物体：

```text
500k triangles
```

可能比：

```text
50k triangles
```

更噪。

---

## 54.6 Splat Removal Ratio

例如：

\[
\frac{15114-9163}{15114}
\approx39.4\%
\]

只能说明 Cleanup 删除了多少。

不能脱离 Raw/Clean 视觉对比直接说：

```text
39.4% 就是好
```

---

# 55. Artifact Inspector 应该成为你的学习主界面

每学习一个理论概念，都回到 GUI 找对应 Artifact。

| 理论 | GUI Artifact |
|---|---|
| Temporal Sampling | Frames |
| Segmentation | Masks / Overlay |
| SfM | COLMAP Sparse |
| MVS | Dense Cloud |
| Surface Reconstruction | Raw Mesh |
| Refinement | Refined Mesh |
| UV / Texture | Texture Atlas |
| glTF Asset | GLB |
| Semantic Sparse Filter | Object Sparse |
| 3DGS | Raw Splat |
| Multi-view Semantic Filter | Clean Splat |

这样你不会陷入：

```text
只会背公式
但不知道项目中对应哪个文件
```

---

# 56. 逐阶段故障树

## A. Frames 就不好

症状：

```text
大量模糊
曝光跳变
覆盖不完整
```

不要先调 OpenMVS / Brush。

应该重新拍视频。

---

## B. Mask 不好

症状：

```text
主体被切掉
背景被包含
后期漂移
```

后果：

```text
Mesh 目标约束异常
Object Sparse 异常
Splat Cleanup 异常
```

---

## C. Sparse Camera 错

症状：

```text
Camera 乱飞
点云重影
模型结构撕裂
```

后面两条 Route 都没有可靠基础。

---

## D. Sparse 好，Dense 差

重点看：

```text
表面纹理是否太少
反光是否严重
拍摄 Baseline
图像分辨率
OpenMVS Dense Settings
```

---

## E. Dense 好，Mesh 差

重点：

```text
Surface Reconstruction
Refine
是否有 Floating Points
是否目标边界过差
```

---

## F. Geometry 好，Texture 差

重点：

```text
相机投影一致性
曝光
遮挡
Texture Atlas
OpenMVS Texture workaround
```

---

## G. Raw Splat 差

重点：

```text
Camera Pose
Object Sparse
Brush Training
输入曝光
Mask Dataset
```

---

## H. Raw 好，Clean 差

重点：

```text
cleanup_ratio
cleanup_min_views
SAM2 边界
```

---

# 57. 拍摄本身就是算法的一部分

再强的算法也不能恢复输入中从未出现的信息。

## 57.1 Coverage

尽量让目标：

```text
前
左前
左
左后
后
右后
右
右前
```

都被看到。

---

## 57.2 相邻帧必须有 Overlap

理想不是：

```text
一张正面
下一张直接背面
```

而是连续变化：

```text
0°
10°
20°
30°
...
```

使 Feature Track 可以连续传播。

---

## 57.3 不要只旋转物体纹理背景完全不动吗？

如果转台拍摄，几何解释会变成：

```text
物体在动
相机不动
```

而传统静态 SfM 假设：

```text
场景静止
Camera 在动
```

这两种相对运动在纯目标理想条件下有关系，但背景不一致会制造冲突。

Videoto3D 当前更适合：

> Camera 围绕静止目标移动。

---

## 57.4 避免强反光

MVS / Feature Matching 大量依赖：

> 同一个真实表面区域在不同 View 中外观具有一定一致性。

强 Specular Highlight 会随视角移动：

```text
物理表面点没变
亮点位置变了
```

这违反简单 Photometric Consistency。

---

# 58. 参数应该怎么调：先知道它影响哪一层

## Mesh

### `undistort_max_image_size`

影响：

```text
进入 OpenMVS 的图像尺寸
```

不影响：

```text
Shared RGB SfM
```

### `dense_resolution_level`

影响：

```text
MVS Depth / Dense
```

变化后：

```text
Dense 以及下游失效
```

### `dense_number_views`

控制 Dense 阶段使用的邻域 View 数策略。

不是简单的：

```text
越多越好
```

更多 View 可能：

- 提供更多一致性证据；
- 也可能引入角度太大/遮挡更多的 View；
- 增加计算。

### `dense_max_threads`

主要影响资源与稳定性。

### `refine_resolution_level`

影响：

```text
Refinement 使用的图像尺度
```

---

## Splat

### `steps`

更多 Iteration：

```text
可能收敛更充分
但耗时增加
```

不保证无限增加永远更好。

### `max_splats`

限制 Representation Capacity。

### `max_resolution`

训练图像尺度。

### `foreground_ratio`

Object Sparse 的前景支持比例阈值。

### `min_foreground_observations`

Object Sparse 至少多少个前景 Observation。

### `cleanup_ratio`

Final Gaussian 前景支持率阈值。

### `cleanup_min_views`

一个 Gaussian 至少被多少 View 有效观察。

---

# 59. 为什么 Recipe-aware Cache 很重要

传统“脚本串联”很容易：

```text
改一个 Cleanup 参数
↓
全部从抽帧重新跑
```

浪费大量时间。

Videoto3D 把 Pipeline 看成依赖图：

```text
Frames
↓
Mask
↓
Sparse
├─ Mesh Dense → Mesh → Refine → Texture → GLB
└─ Splat Train → Cleanup → PLY
```

如果只改变 Cleanup：

```text
只让 Cleanup / Final PLY 失效
```

这是构建系统里的思想：

> **Incremental Rebuild / Dependency Invalidation**

而不仅是计算机视觉。

---

# 60. `run.json` 的意义

`run.json` 不是 3D 数据本身。

它更像：

```text
这个 Run 的状态机 / Manifest
```

记录：

```text
source
shared stages
mesh stages
splat stages
paths
status
metadata
```

Artifact Inspector 进一步要求：

> Manifest 说 Ready 不够，实际文件也应该存在。

因此 V1.2.0 状态有：

```text
READY
PARTIAL
PENDING
MISSING
```

---

# 61. 你应该掌握的知识树

```text
Videoto3D
│
├─ Image Formation
│  ├─ Pinhole Camera
│  ├─ Intrinsics
│  ├─ Extrinsics
│  ├─ Homogeneous Coordinate
│  └─ Distortion
│
├─ Feature Geometry
│  ├─ Keypoint
│  ├─ Descriptor
│  ├─ Matching
│  ├─ Epipolar Geometry
│  ├─ Essential Matrix
│  ├─ Fundamental Matrix
│  └─ RANSAC
│
├─ SfM
│  ├─ Relative Pose
│  ├─ Triangulation
│  ├─ PnP
│  ├─ Track
│  ├─ Incremental Mapping
│  └─ Bundle Adjustment
│
├─ MVS
│  ├─ Depth
│  ├─ Baseline
│  ├─ Photometric Consistency
│  ├─ Depth Fusion
│  └─ Dense Point Cloud
│
├─ Mesh
│  ├─ Vertex
│  ├─ Face
│  ├─ Normal
│  ├─ Surface Reconstruction
│  ├─ Refinement
│  ├─ UV
│  └─ Texture Atlas
│
├─ Segmentation
│  ├─ Prompt
│  ├─ SAM2 Video Memory
│  ├─ Mask Logit
│  └─ Mask Propagation
│
├─ Gaussian Splatting
│  ├─ Mean
│  ├─ Covariance
│  ├─ Scale
│  ├─ Quaternion
│  ├─ Projection Jacobian
│  ├─ Alpha Compositing
│  ├─ Spherical Harmonics
│  └─ Training / Densification
│
└─ Engineering
   ├─ Run Manifest
   ├─ Artifact Inspector
   ├─ Quality Report
   ├─ Recipe Cache
   ├─ Local Environments
   └─ Reusable Viewer
```

---

# 62. 公式速查表

## World → Camera

\[
\mathbf X_c
=
R\mathbf X_w+t
\]

## Pinhole

\[
x=X/Z,\qquad y=Y/Z
\]

## SIMPLE_RADIAL

\[
r^2=x^2+y^2
\]

\[
x_d=x(1+kr^2)
\]

\[
y_d=y(1+kr^2)
\]

\[
u=fx_d+c_x,\qquad
v=fy_d+c_y
\]

## Camera Matrix

\[
\lambda\tilde x
=
K[R|t]\tilde X
\]

## Essential Matrix

\[
E=[t]_\times R
\]

\[
x_2^\top E x_1=0
\]

## Fundamental Matrix

\[
F=K_2^{-\top}EK_1^{-1}
\]

\[
u_2^\top F u_1=0
\]

## Triangulation

\[
x\times(PX)=0
\]

## Reprojection Error

\[
e=
\|x-\pi(P,X)\|_2
\]

## Bundle Adjustment

\[
\min
\sum_{ij}
\rho
\left(
\|x_{ij}-\pi(\Theta_i,X_j)\|^2
\right)
\]

## Stereo Depth

\[
Z=\frac{fB}{d}
\]

## Gaussian

\[
G(x)
=
\exp
\left(
-\frac12
(x-\mu)^\top
\Sigma^{-1}
(x-\mu)
\right)
\]

## Gaussian Covariance

\[
\Sigma
=
RSS^\top R^\top
\]

## Perspective Jacobian

\[
J=
\begin{bmatrix}
f_x/Z&0&-f_xX/Z^2\\
0&f_y/Z&-f_yY/Z^2
\end{bmatrix}
\]

## 2D Gaussian Approximation

\[
\Sigma_{2D}
\approx
J R_c\Sigma R_c^\top J^\top
\]

## Alpha Compositing

\[
T_i=\prod_{j<i}(1-\alpha_j)
\]

\[
C=\sum_i T_i\alpha_i c_i
\]

## Object / Cleanup Foreground Support

\[
r_j
=
\frac{F_j}{V_j}
\]

---

# 63. 一道贯穿全项目的思考题

假设最终 `ceramics_doll` 的 Clean Splat 缺掉右手。

不要立即改：

```text
Brush steps
```

请沿 Pipeline 倒查：

```text
Clean Splat
↓
Raw Splat 是否有右手？
↓
如果 Raw 有：
    Cleanup 投影票数是否不足？
    SAM2 右手在多少视角被 Mask 切掉？
↓
如果 Raw 就没有：
    Object Sparse 是否有右手附近 3D Points？
↓
如果 Object Sparse 没有：
    Shared Sparse 是否有？
↓
如果 Shared Sparse 也没有：
    COLMAP Feature / Camera coverage / 拍摄是否不足？
↓
Frames 中右手是否真正被多个视角看到？
```

这就是你真正掌握 Pipeline 后应该形成的思维方式：

\[
\boxed{
\text{Final Error}
\rightarrow
\text{Trace upstream evidence}
}
\]

而不是：

\[
\text{Final Error}
\rightarrow
\text{Random parameter tuning}
\]

---

# 64. 推荐学习顺序

第一阶段：

```text
Camera Projection
Intrinsics / Extrinsics
SIMPLE_RADIAL
Reprojection Error
```

第二阶段：

```text
Feature
Matching
Epipolar Geometry
RANSAC
```

第三阶段：

```text
SfM
Triangulation
PnP
Bundle Adjustment
```

第四阶段：

```text
MVS
Depth
Dense
Mesh
Texture
```

第五阶段：

```text
3D Gaussian
Covariance
Projection
Alpha Blending
SH
```

第六阶段：

```text
SAM2
Object Sparse
Cleanup
Artifact Debugging
```

每学一章，就打开 Videoto3D 找对应 Artifact。

---

# 65. 与当前 Videoto3D 实现对应的源码入口

想进一步从理论进入代码：

```text
pipeline/video.py
→ FFmpeg 抽帧

scripts/sam2_mask_worker.py
pipeline/segmentation.py
→ SAM2

pipeline/colmap.py
→ Feature / Matching / Sparse SfM

pipeline/openmvs.py
→ Undistort / OpenMVS Mesh Route

pipeline/colmap_object.py
→ Object Sparse 多视角 Mask 投票

pipeline/brush.py
→ Brush Dataset / Training

pipeline/splat_cleanup.py
→ Final Gaussian Multi-view Cleanup

pipeline/quality.py
→ Quality Report

gui/control/server/artifacts.py
→ Artifact Inspector 后端

gui/viewer/
→ 通用 GLB / PLY / Splat 浏览器 Viewer
```

理论和代码对应起来以后，这个项目才真正变成你的知识体系。

---

# 66. 参考资料

下面优先列官方项目、官方文档和原始论文：

1. **COLMAP Camera Models / Projection**  
   https://colmap.github.io/cameras.html

2. **COLMAP Repository**  
   https://github.com/colmap/colmap

3. **OpenMVS Repository**  
   https://github.com/cdcseacave/openMVS

4. **SAM 2 Repository**  
   https://github.com/facebookresearch/sam2

5. **SAM 2: Segment Anything in Images and Videos**  
   https://arxiv.org/abs/2408.00714

6. **Brush Gaussian Splatting Engine**  
   https://github.com/ArthurBrussee/brush

7. **3D Gaussian Splatting for Real-Time Radiance Field Rendering**  
   https://arxiv.org/abs/2308.04079

8. **3DGS Project Page**  
   https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/

---

# 67. 最终目标

当别人问：

> “Videoto3D 为什么能从视频恢复 3D？”

你应该能完整回答：

```text
视频提供连续多视角。
FFmpeg 把它离散成 Frame。

SAM2 根据第一帧的 Prompt 传播主体 Mask，
但 Shared SfM 保留完整 RGB，
因为背景 Feature 对 Camera Pose 估计有帮助。

COLMAP 在不同 Frame 中提取并匹配局部 Feature，
用 Epipolar Geometry + RANSAC 建立可靠几何 Correspondence，
通过 Incremental SfM、Triangulation、PnP 和 Bundle Adjustment
联合恢复 Camera Intrinsics、Camera Poses 和 Sparse 3D Points。

Mesh Route 使用这些 Camera Geometry 做 Undistort，
OpenMVS 再利用多视角 Photometric / Geometric Consistency
恢复 Dense Point Cloud，生成和优化 Triangle Mesh，
最后把多视角照片映射成 Texture，并导出 GLB。

Splat Route 则用 Sparse Geometry 初始化 3D Gaussian。
Videoto3D 先利用 SAM2 Mask 对 Sparse Track 做多视角投票，
减少背景初始化。
Brush 根据所有已知 Camera View 优化 Gaussian 的位置、形状、
透明度和外观，使渲染结果逼近输入照片。
训练结束后，Videoto3D 再把每个 Final Gaussian Center
投影回多个 COLMAP Camera，并查询对应 SAM2 Mask。
只有得到足够多前景视角支持的 Gaussian 才保留，
最终得到 Clean Gaussian PLY。
```

能够把这条逻辑和对应数学讲清楚时，你就已经从：

```text
“会运行几个 3D 工具”
```

进入：

```text
“理解一条完整 Multi-View Reconstruction Pipeline”
```

---

# 68. V1.3 Turntable Capture Mode：固定相机为什么也能做刚体 3D

V1.2 的默认采集模型是：

```text
Object static
Camera moves
```

V1.3 增加：

```text
Camera static
Rigid object rotates
```

对刚体而言，图像约束来自相机与物体之间的**相对位姿**。设物体到相机的齐次变换为：

\[
T_{co}(t)=
\begin{bmatrix}
R_o(t) & t_o(t)\\
0 & 1
\end{bmatrix}
\]

如果把物体坐标系定义成静止世界坐标系，同一组相对观测可以写成等效相机运动：

\[
T_{oc}(t)=T_{co}(t)^{-1}
\]

因此“物体旋转”可以被 SfM 解释成“相机反向绕物体运动”。

## 68.1 为什么完整 RGB 在 Turntable 下会冲突

背景固定时，背景点满足近似零光流：

\[
\Delta u_{bg}\approx0,\qquad \Delta v_{bg}\approx0
\]

而物体表面特征随旋转产生显著对应变化。如果 Feature Extraction 同时覆盖背景与主体，静止背景往往提供数量更多、稳定性更高的匹配，从而把问题推向“相机没有移动”的退化解释。

V1.3 使用逐帧 SAM2 二值 Mask：

\[
M_t(u,v)\in\{0,1\}
\]

Feature 只允许出现在：

\[
\mathcal F_t=\{f_i\mid M_t(u_i,v_i)=1\}
\]

这样 Sequential Matching、Essential/Fundamental Geometry、Triangulation 与 Bundle Adjustment 主要由刚体主体自身的跨帧特征支撑。

## 68.2 不是把背景像素改黑

V1.3 保留原始 RGB：

```text
RGB image = unchanged
SAM2 mask = separate file
COLMAP ImageReader.mask_path = masks/
```

Mask 控制“哪里可以提 Feature”，而不是创造一套新的黑背景照片。这样避免人为边界进入图像内容，同时继续保留真实主体像素。

## 68.3 Camera Center

COLMAP 的外参采用 world-to-camera：

\[
x_c=Rx_w+t
\]

相机中心满足：

\[
0=RC+t
\]

因此：

\[
\boxed{C=-R^Tt}
\]

Artifact Inspector 的 Camera Trajectory 读取每个注册图像的 \(q,t\)，把 quaternion 转成 \(R\)，再计算 \(C\) 并输出为浏览器可读 PLY 点云。

对于正常 Orbit Camera，它表示真实相机中心轨迹；对于 Turntable，它表示由刚体旋转恢复出的**等效虚拟相机轨迹**。

## 68.4 人体边界

如果人物只是整体旋转且姿态近似不变，可以近似看成刚体。但以下变化会破坏单一静态几何假设：

```text
手臂独立运动
走路
头部相对身体转动
明显表情变化
头发 / 衣物大幅变形
```

这些属于 Dynamic / 4D Reconstruction，而不是 V1.3 Turntable 的目标问题。

