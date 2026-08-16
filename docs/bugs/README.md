# Videoto3D Bug / Incident Registry

这个目录用于记录**已经影响工程行为的真实 Bug、上游缺陷、兼容性问题和重要事故**。目标不是堆积报错日志，而是保存可复现、可追踪、可验证、可移除的工程知识，避免同一问题在后续版本反复调查。

## 记录原则

每个值得长期保留的问题使用独立文件：

```text
BUG-0001-short-description.md
BUG-0002-short-description.md
...
```

每条记录至少包含：

- **Status**：Open / Investigating / Mitigated / Resolved / Closed
- **Severity**：Low / Medium / High / Critical
- **Affected**：受影响的 Videoto3D / 第三方版本
- **Symptom**：用户实际看到的现象
- **Reproduction**：最小复现步骤
- **Evidence**：日志、退出码、A/B 实验结果
- **Root cause**：已证实的根因；未证实时明确写“Hypothesis”
- **Workaround / Fix**：当前工程采取的处理方式
- **Regression guard**：防止复发的测试、缓存版本或检查
- **Upstream**：第三方 issue / commit / release
- **Removal condition**：临时 workaround 何时可以安全移除

## 生命周期

```text
Open → Investigating → Mitigated → Resolved → Closed
```

- **Mitigated**：已有可靠 workaround，但根因仍在上游或尚未永久修复。
- **Resolved**：根因已修复且通过回归验证。
- **Closed**：修复已进入稳定基线，文档仅作为历史记录保留。

不要删除历史 Bug 文件；状态变化直接更新原文件，并在根 README 的版本记录中留下对应版本号。

## 当前索引

| ID | 状态 | 严重度 | 摘要 | 当前处理 |
|---|---|---:|---|---|
| [BUG-0001](BUG-0001-openmvs-2.4.0-texture-black-artifacts.md) | Mitigated | High | OpenMVS 2.4.0 TextureMesh seam leveling 产生大面积黑纹理 | V0.7.3 临时关闭 global/local seam leveling，等待升级含上游修复的 runtime |
| [BUG-0002](BUG-0002-viewer-process-does-not-release-terminal.md) | Resolved | Medium | GUI Viewer 继承终端句柄，关闭后仍需 Ctrl+C | V0.9 统一 detached viewer process |
| [BUG-0003](BUG-0003-conda-env-create-yes-flag-compatibility.md) | Resolved | High | V1.0.1 项目内 Conda bootstrap 给 `conda env create/update` 传入不兼容的 `-y` | V1.0.1 Hotfix 1 移除该参数并增加命令兼容性回归测试 |
| [BUG-0004](BUG-0004-web-viewer-cannot-roll-upright.md) | Resolved | Medium | Web Viewer 固定 up 导致倒置资产无法自由滚转到正确朝向 | V1.0.2 改为 TrackballControls + Roll/Flip 控件 |
| [BUG-0005](BUG-0005-trackball-controls-keys-typescript-build.md) | Resolved | High | TrackballControls `keys=[]` 不满足 three.js 三元组类型，导致 GUI `tsc -b` 构建失败 | V1.0.2 Hotfix 1 改为固定长度空字符串三元组并加回归测试 |
| [BUG-0006](BUG-0006-gui-ctrl-c-parent-child-shutdown.md) | Resolved | Medium | GUI core/gui 子进程链下 Ctrl+C 生命周期不可靠 | V1.1 父进程显式请求 graceful shutdown 并提供 fallback |

| [BUG-0007](BUG-0007-core-environment-missing-pillow.md) | Resolved | High | V1.1.1 `env/core` recipe 漏掉 Mask validation 所需 Pillow | V1.1.2 将 Pillow 固化到 core recipe + PIL health probe |

## 新问题模板

复制 [`_TEMPLATE.md`](_TEMPLATE.md)，分配下一个连续 BUG ID，并在本索引中增加一行。
