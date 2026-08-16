# BUG-0005 — TrackballControls keys 空数组导致 TypeScript build 失败

- **Status:** Resolved
- **Severity:** High
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** V1.0.2 Web Viewer
- **Fixed/Mitigated in:** V1.0.2 Hotfix 1
- **Upstream:** three.js TrackballControls type contract (`keys: [string, string, string]`)

## Summary

V1.0.2 为禁用 TrackballControls 的 A/S/D 键盘模式切换，将 `controls.keys` 赋值为空数组，运行意图正确但违反 three.js TypeScript 固定长度三元组类型，导致 `npm run build` 在 `tsc -b` 阶段失败。

## Symptom

```text
../../viewer/src/AssetViewer.tsx:64:5 - error TS2322:
Type '[]' is not assignable to type '[string, string, string]'.
```

因此 `python app.py gui` 自动检测到前端源码变化后能够完成 `npm install`，但在 `npm run build` 中止，Studio 无法启动新 Viewer。

## Reproduction

```text
1. 覆盖 V1.0.2。
2. 执行 python app.py gui。
3. GUI 自动执行 npm run build。
4. tsc -b 在 AssetViewer.tsx 的 controls.keys = [] 处失败。
```

## Evidence

Windows 实机错误明确报告 `TrackballControls.keys` 目标类型为 `[string, string, string]`，而 V1.0.2 传入 `[]`。

## Root cause

three.js 的 `TrackballControls.keys` 是固定长度三元组，用三个槽位分别表示 rotate / zoom / pan 的键盘临时模式键。V1.0.2 为完全禁用这些键而赋值 `[]`，没有满足 TypeScript 类型约束。

## Workaround / Fix

保留禁用键盘模式切换的行为，但使用合法三元组：

```ts
controls.keys = ['', '', '']
```

空字符串不会匹配正常的 `KeyboardEvent.code`，同时满足 three.js 的固定长度类型。

## Regression guard

`tests/test_gui_viewer_trackball_types.py` 要求 Viewer 使用三个空字符串，并禁止重新出现 `controls.keys = []`。

## Verification

- 回归测试先在 V1.0.2 原始代码上失败。
- 修改为固定长度空字符串三元组后 focused test 通过。
- 完整 Python suite 与 `compileall` 作为交付门禁。
- Windows 真实 `npm run build` 需要在用户机器上再次验证，因为交付容器没有项目 npm 依赖缓存。

## Risks / Trade-offs

无新增运行时依赖。A/S/D 临时控制模式被禁用；鼠标 Trackball、Roll/Flip 和工具栏视角不受影响。

## Removal condition

除非 three.js 将 `TrackballControls.keys` API 改为可选/可变长度，否则保持当前固定长度禁用值。

## Timeline

- 2026-08-17 — Windows 实机 `tsc -b` 发现 TS2322。
- 2026-08-17 — 根因确认并以合法三元组修复。
