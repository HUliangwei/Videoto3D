# Turntable Capture Mode · V1.3.1

Turntable 的目标不是增加更多参数，而是让一种很明确的采集方式稳定进入现有两条重建路线。

## 推荐拍摄

```text
Camera     固定
Subject    刚体
Rotation   约 360°
Speed      基本匀速
Video      尽量只包含这一整圈
Framing    主体居中
Camera     尽量保持水平，不明显俯拍/仰拍
```

推荐把开始前等待、结束后等待剪掉。Videoto3D 会把全部抽取帧按时间顺序均匀映射到一整圈。

## Pipeline

```text
Video
→ Frames
→ SAM2 Masks
→ Mask-guided Features
→ Matching
→ Uniform 360° Known Poses
→ CW / CCW Triangulation
→ Best Sparse Model
├→ Mesh Route → GLB
└→ Splat Route → Clean PLY
```

无需手动选择旋转方向：程序会尝试两个方向并选择稀疏点支持更强的结果。

## 不适合

明显非匀速反复转动、不到一整圈又倒转、相机同时移动、人物明显改变姿态、衣服/头发大幅运动，都不符合该模式假设。
