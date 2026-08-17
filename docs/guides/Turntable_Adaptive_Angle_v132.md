# Turntable Adaptive Angle · V1.3.2

V1.3.2 不再要求转台匀速。

推荐拍摄仍然是：

```text
Camera   固定
Subject  刚体
Motion   单方向转约 360°
Video    尽量只保留这一整圈
```

允许：

```text
慢 → 快 → 慢 → 稍快 → 慢
```

不建议：

```text
正转 → 停很久 → 反转 → 再正转
```

内部流程：

```text
SAM2 Mask-guided Features
→ COLMAP Two-view Geometry
→ Adjacent Δθ
→ Robust Smoothing
→ Normalize Full Turn
→ Adaptive Known Poses
→ CW / CCW Triangulation
→ Shared Sparse
├→ Mesh Route
└→ Splat Route
```

诊断文件：

```text
workspace/runs/<run_id>/colmap/turntable_angle_report.json
```

重点字段：
- `strategy`: `adaptive_360_epipolar` 或 `uniform_360_fallback`
- `valid_pair_ratio`
- `raw_increment_deg`
- `normalized_increment_deg`
- `cumulative_angle_deg`

如果 `valid_pair_ratio` 很低，说明相邻主体特征不足，程序会自动退回 uniform 模式。
