# BUG-0001 — OpenMVS 2.4.0 TextureMesh produces black texture artifacts

- **Status:** Mitigated
- **Severity:** High
- **Detected:** 2026-08-16
- **Owner:** Videoto3D
- **Affected:** OpenMVS x64 v2.4.0 (Build date 2026-01-20); Videoto3D V0.7–V0.7.2 texture stage
- **Mitigated in:** Videoto3D V0.7.3
- **Upstream:** https://github.com/cdcseacave/openMVS/issues/1251

## Summary

OpenMVS 2.4.0 的 `TextureMesh` 在默认开启 seam leveling 时会生成大面积近黑纹理 patch。几何重建正常，但最终 OBJ/GLB 表面几乎全黑，只剩少量正常颜色和 patch 边界。

## Symptom

Videoto3D 的 SAM2 → COLMAP → mask-aware Densify → ReconstructMesh → RefineMesh 均成功，小熊几何明显改善；但 `object_material_00_map_Kd.jpg` 包含大量黑色区域，Blender 只是忠实显示该错误 atlas。

典型命令：

```text
TextureMesh ... --ignore-mask-label 0
```

默认：

```text
--global-seam-leveling 1
--local-seam-leveling 1
```

## Reproduction and evidence

1. OpenMVS 2.4.0 默认 TextureMesh：atlas 大面积黑色。
2. `--ignore-mask-label -1`：问题仍存在，说明不是 SAM2 label 取值本身导致。
3. `--ignore-mask-label -2`：Windows 退出码 `-1073741819`（`0xC0000005`, Access Violation），不能作为 workaround。
4. 保持 `--ignore-mask-label 0`，同时执行：

```text
--global-seam-leveling 0
--local-seam-leveling 0
```

纹理恢复为正常的小熊毛发、衣物、帽子等颜色。代价是 patch 之间缺少 seam leveling，整体接缝/色差质量低于理想状态。

该 A/B 结果与 OpenMVS upstream issue #1251 的复现与 workaround 一致。

## Root cause

上游 issue #1251 最终定位到 OpenMVS v2.4.0 `libs/Common/Types.inl` 的图像采样模板参数回归。v2.4.0 中：

```cpp
return Sampler::Sample<
    INTERTYPE, INTERTYPE, TImage<TYPE>, SAMPLER,
    TPoint2<typename SAMPLER::Type>
>(*this, sampler, pt);
```

上游讨论给出的修复是第一个模板参数应为 `TYPE`：

```cpp
return Sampler::Sample<
    TYPE, INTERTYPE, TImage<TYPE>, SAMPLER,
    TPoint2<typename SAMPLER::Type>
>(*this, sampler, pt);
```

OpenMVS 维护者随后确认将加入修复并要求检查最新 `develop`；当前 develop 已包含这一修正。

因此，本问题不是 Blender、SAM2 分割质量或 COLMAP 相机位姿造成的；它属于 OpenMVS 2.4.0 TextureMesh 上游回归。

## Workaround in Videoto3D V0.7.3

继续让 DensifyPointCloud 使用目标 Mask：

```text
--mask-path <openmvs_masks>
--ignore-mask-label 0
```

TextureMesh 同样保留 `--ignore-mask-label 0`，但临时禁用两种 seam leveling：

```text
--global-seam-leveling 0
--local-seam-leveling 0
```

这是 upstream issue 中已实测可恢复正确颜色的 workaround。

## Regression guard

V0.7.3 增加三层保护：

1. 单元测试强制 `build_texture_mesh_args()` 包含两个 seam-leveling `0` 参数。
2. `openmvs/texture_recipe.json` 记录当前 texture recipe 版本和参数。
3. 旧 V0.7/V0.7.2 `object.obj` 没有当前 recipe marker，因此升级到 V0.7.3 后 `python app.py run mesh` 会**只重跑 TextureMesh**，不会错误复用黑纹理缓存，也不会重跑已经完成的 Dense/Mesh/Refine。

当前 recipe version：

```text
openmvs-2.4.0-seam-leveling-off-v1
```

## Verification

2026-08-16 实机：

- RTX 4060 Laptop / Windows 11
- OpenMVS x64 v2.4.0
- 114 calibrated images
- `scene_refined.ply`: 25,373 vertices / 50,652 faces
- 默认 seam leveling：黑色 atlas
- global/local seam leveling 均为 `0`：真实小熊纹理恢复

## Risks / Trade-offs

此 workaround 恢复正确颜色，但关闭 seam leveling 后，不同 texture patches 之间可能出现更明显的亮度/色差接缝。因此它是**稳定性优先的临时 mitigation**，不是最终高质量纹理方案。

## Removal condition

当 Videoto3D 的 OpenMVS runtime 升级到包含 upstream sampler 修复的版本/commit 后：

1. 恢复 `--global-seam-leveling 1` 与 `--local-seam-leveling 1`（或移除显式 `0` 使用已修复默认值）。
2. 使用当前 teddy baseline 重新跑 TextureMesh A/B。
3. 验证 atlas 无大面积黑块，Blender Mesh 纹理正常，并确认 `--ignore-mask-label -2` 等路径是否仍有独立崩溃风险。
4. 更新本文件状态为 Resolved/Closed，并提升 `TEXTURE_RECIPE_VERSION` 使旧 workaround cache 自动失效。

## Timeline

- 2026-08-16 — 发现 Mesh 几何正常但 Texture atlas 大面积黑色。
- 2026-08-16 — `ignore-mask-label -1` 未改善；`-2` 触发 `0xC0000005`。
- 2026-08-16 — 对照 upstream issue #1251，确认 OpenMVS 2.4.0 已知 TextureMesh regression。
- 2026-08-16 — 关闭 global/local seam leveling 后实机纹理恢复正常。
- 2026-08-16 — V0.7.3 将 workaround、cache recipe marker、回归测试和 Bug Registry 固化到工程。
