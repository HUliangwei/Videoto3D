# BUG-XXXX — 简短标题

- **Status:** Investigating
- **Severity:** Medium
- **Detected:** YYYY-MM-DD
- **Owner:** Videoto3D
- **Affected:**
- **Fixed/Mitigated in:**
- **Upstream:**

## Summary

一句话描述问题和影响。

## Symptom

用户实际看到什么；避免只写内部推测。

## Reproduction

```text
1. ...
2. ...
3. ...
```

## Evidence

记录关键日志、退出码、A/B 结果、输入输出路径。不要把大体积二进制直接提交到仓库；只记录可定位它们的 workspace 路径或摘要。

## Root cause

如果已经证实，写证据链；如果尚未证实，标题改为 `Hypothesis` 并明确不确定性。

## Workaround / Fix

说明当前代码采取的最小处理方式，以及为什么这样做。

## Regression guard

列出对应测试、版本 marker、cache invalidation 或运行时检查。

## Verification

记录修复后的实机验证条件和结果。

## Risks / Trade-offs

临时方案带来的质量、性能或兼容性代价。

## Removal condition

写清楚什么时候可以移除 workaround，以及移除前必须跑哪些验证。

## Timeline

- YYYY-MM-DD — Detected.
- YYYY-MM-DD — Root cause confirmed.
- YYYY-MM-DD — Mitigation shipped.
