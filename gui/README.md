# Videoto3D GUI Module

`gui/` 与 reconstruction core 保持模块边界。V1.1.2 的 `control/` 已成为本地操作台：New Run、视频导入、浏览器 SAM2 ROI、Mesh/Splat Route、sticky 任务进度与可折叠实时日志；`viewer/` 仍是可独立迁移的 type+src 3D Viewer。

## Boundary

```text
Core (app.py + pipeline/)          GUI module
                                   ├─ control/  Videoto3D-specific
run.json ◀──────────── read/write ─▶│  ├─ server/ FastAPI bridge
quality/report.json ─────read─────▶│  └─ web/    Studio UI
GLB / PLY ───────────────serve────▶│
                                   └─ viewer/   reusable 3D asset viewer
```

### `control/`

May know about Videoto3D concepts: Runs, Shared, Mesh Route, Splat Route, quality reports, the local API, and Studio lifecycle.

### `viewer/`

must **not** know about Videoto3D. Its public contract remains generic:

```tsx
<AssetViewer type="glb" src="/model.glb" />
<AssetViewer type="splat" src="/model.ply" />
```

It uses Three.js TrackballControls for free orbit/roll plus RMB pan and wheel zoom, and provides double-click focus, Fit, six axis views, Iso, Roll Left / Flip / Roll Right, Auto Rotate and Fullscreen controls. The folder can later be copied/published for a personal website or another project.

## Runtime

Normal users do not install GUI Python dependencies manually. From the project root:

```powershell
python app.py gui
```

Videoto3D automatically provisions `env/core` and `env/gui` from `config/envs/`, and automatically runs `npm install` + `npm run build` when the frontend build is missing/stale.

Conda must already be installed on the machine (A1 policy); verify with `conda --version`. Node.js/npm remains the external JavaScript toolchain prerequisite. V1.1 reports a concise `[PREREQ][MISSING] Conda` message if the A1 prerequisite is absent.

## Stop Studio

Recommended: click **Exit Studio** in the top-right corner. The Control Web calls the explicit shutdown API and Uvicorn exits gracefully. `Ctrl+C` remains a fallback. Closing or refreshing a normal browser tab never means shutdown.

## Viewer-only demo

```powershell
cd gui
npm run viewer:dev
```

Use `?type=glb&src=<url>` or `?type=splat&src=<url>`.

## Progress UX (V1.1.2)

`control/server/progress.py` 只读取 run-local 文件、manifest 与日志，给 Control Web 提供可信 progress snapshot。SAM2/Brush 有可靠计数时显示百分比；OpenMVS 等只显示 stage stepper。`viewer/` 不依赖 progress/job API。

## V1.1.2 Control additions

- Mesh Settings: safe OpenMVS profile with recipe-aware rerun.
- Paths & Runtime: read-only project/environment/tool/run path inspector with Copy Path.
- OpenMVS 2.4.0 seam-leveling workaround remains locked OFF.
