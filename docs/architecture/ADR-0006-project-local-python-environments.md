# ADR-0006: Project-local Python Environments

## Status

Accepted — Videoto3D V1.0.1.

## Decision

Videoto3D owns three Conda prefix environments under the project root:

- `env/core`
- `env/seg`
- `env/gui`

Conda itself remains an external prerequisite (A1). The project does not download or embed Miniconda. Recipes live in `config/envs/`; generated environments are local machine state and ignored by Git.

The outer Python process is only a bootstrap. On Windows `python app.py ...` ensures `env/core`, then re-executes the same command with `env/core/python.exe`. Segmentation and GUI environments are created lazily only when required.

`runtime/` continues to contain third-party executables, source trees and model checkpoints; `workspace/` continues to contain user Run data. Repairing one environment may not modify either directory or another environment.

## Rationale

This prevents FastAPI/Jupyter/Spyder and PyTorch/SAM2 dependency collisions in the user's system Anaconda while preserving one-command operation. Prefix environments also keep the environment physically associated with the project instead of depending on machine-specific named Conda environment paths.

## GUI lifecycle

The GUI server runs under `env/gui`. Browser tab close/refresh is not a shutdown signal. The Control Web exposes an explicit `Exit Studio` action backed by `POST /api/system/shutdown`; Uvicorn performs graceful shutdown. `Ctrl+C` remains a fallback.

## Viewer boundary

Viewer navigation improvements belong to `gui/viewer` because they are generic and portable. The viewer remains independent from Videoto3D Run/API concepts.
