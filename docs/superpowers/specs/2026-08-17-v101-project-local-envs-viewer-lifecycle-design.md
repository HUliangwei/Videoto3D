# Videoto3D V1.0.1 Project-Local Environments + Viewer Lifecycle Design

## Goal

Make Videoto3D self-manage all Python environments under the project root while keeping Conda as the only external Python-environment prerequisite, and finish the GUI foundation with reusable camera controls and explicit graceful Studio exit.

## Frozen Architecture

- `env/core`: project core Python 3.11 environment. The outer Python only bootstraps this environment, then re-executes `app.py` inside it.
- `env/seg`: SAM2/PyTorch CUDA environment, created lazily when segmentation is first required.
- `env/gui`: FastAPI/Uvicorn environment, created lazily when `python app.py gui` is first required.
- `runtime/`: remains third-party executable/model/source storage; SAM2 repo and checkpoints remain here.
- `workspace/`: remains user task data.
- `config/envs/*.yml`: committed environment recipes; `env/` itself is local and ignored.

Conda is discovered from `CONDA_EXE`, PATH, and common Windows Anaconda/Miniconda locations. If Conda cannot be found, bootstrap stops with a clear A1 prerequisite message rather than downloading Conda.

## Bootstrap Flow

`python app.py <command>` from any Python installation:

1. `app.py` executes a stdlib-only bootstrap before importing NumPy/FastAPI-dependent project modules.
2. Bootstrap checks `env/core/.videoto3d-env.json` against the core recipe hash.
3. Missing/stale core environment is created/updated under `env/core` using Conda.
4. The current process is replaced by `env/core/python.exe app.py <same args>`.
5. Inside core, commands execute normally.
6. Segmentation and GUI commands lazily call the same environment manager for `env/seg` or `env/gui`.

Environment state markers record schema, environment name, recipe hash, Python path and readiness. A recipe change causes an in-place environment update rather than silent reuse.

## Environment Recipes

- Core: Python 3.11, pip, NumPy required by Splat Cleanup.
- GUI: Python 3.11 + packages in `gui/control/server/requirements.txt`.
- Seg: Python 3.11 + CUDA-enabled PyTorch 2.5.1/torchvision 0.20.1 cu121 + project-local SAM2 editable install and OpenCV. On Windows SAM2 editable installation sets `SAM2_BUILD_CUDA=0` so the optional SAM2 CUDA extension does not block setup; CUDA PyTorch inference remains required and runtime validation still checks `torch.cuda.is_available()`.

## CLI

Normal users still use `python app.py ...` and do not activate any project environment manually.

Engineering commands:

- `python app.py env status`
- `python app.py env repair core`
- `python app.py env repair seg`
- `python app.py env repair gui`

`repair` recreates only the selected `env/<name>` and never touches runtime/workspace/other environments.

## GUI Runtime

`python app.py gui` from core:

1. ensure `env/gui`;
2. if current interpreter is not GUI Python, launch the GUI server through `env/gui/python.exe`;
3. serve the existing built React application;
4. keep Ctrl+C as a fallback;
5. expose an explicit `POST /api/system/shutdown` used only by the Studio's `Exit Studio` button.

Closing or refreshing a browser tab does not stop the server. Clicking `Exit Studio` triggers graceful Uvicorn shutdown and shows a stopped page.

## Reusable Viewer Controls

`gui/viewer` remains Videoto3D-independent and adds a shared controller for both GLB and Splat:

- LMB rotate
- RMB pan
- wheel zoom
- double-click focus
- Fit
- Reset
- Front / Back / Left / Right / Top / Bottom / Iso
- Auto Rotate toggle
- Fullscreen
- compact interaction hint

The viewer API remains generic (`type`, `src`, optional display settings) and contains no Run, COLMAP, OpenMVS or API knowledge.

## Testing

TDD coverage includes:

- project-local path resolution and recipe hashing;
- Conda discovery and A1 error;
- core bootstrap re-exec behavior without triggering during imports/tests;
- lazy GUI/seg environment creation and repair isolation;
- segmentation runtime now resolves `env/seg/python.exe` rather than machine-specific config Python;
- GUI launcher dispatches through `env/gui`;
- explicit shutdown API sets server exit flag;
- frontend contracts for Exit Studio and reusable viewer controls;
- full Python regression, compileall, TypeScript syntax parse, fresh V1.0 -> V1.0.1 overlay.
