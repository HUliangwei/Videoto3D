# BUG-0008 — Root pytest enters project environments and TestClient lacks HTTPX

- **Status:** Mitigated
- **Severity:** Medium
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** V1.3.0 development/test workflow on Windows
- **Fixed/Mitigated in:** V1.3.0 Hotfix 1
- **Upstream:** pytest discovery / FastAPI TestClient dependency

## Summary

Running `python -m pytest -q` from the repository root had two independent test-harness problems:

1. With no pytest configuration, root discovery could recurse into the project-local `env/` tree.
2. The outer developer Python used to launch pytest had FastAPI/Starlette available but did not have HTTPX, which is required by `fastapi.testclient.TestClient`.

Neither symptom demonstrated a failure in the V1.3 Turntable reconstruction code.

## Symptom

First failure:

```text
env\core\Lib\site-packages\numpy\...
_multiarray_umath.cp311-win_amd64.pyd
Python 3.9 from C:\ProgramData\Anaconda3\python.exe
```

The outer Python 3.9 process discovered packages from `env/core`, whose Python is 3.11.

After restricting collection to `tests/`, collection advanced and failed only on GUI API tests:

```text
ModuleNotFoundError: No module named 'httpx'
RuntimeError: The starlette.testclient module requires the httpx package to be installed.
```

## Reproduction

```powershell
python -m pytest -q
python -m pytest tests -q
.\env\core\python.exe --version
```

Observed on 2026-08-17:

```text
V1.3 focused tests: 9 passed
env/core Python: 3.11.15
outer pytest Python: 3.9.13
no pytest.ini / pyproject pytest config
```

## Evidence

The V1.3 focused suite completed successfully before the full-suite collection problem:

```text
9 passed in 0.54s
```

Root discovery then entered `env/core` and encountered CPython 3.11 NumPy extension files from a CPython 3.9 process.

Explicit `tests/` discovery avoided that problem and exposed the separate missing HTTPX development dependency.

## Root cause

Two test-harness configuration gaps:

- Repository root had no `pytest.ini`, so project-local environments were not excluded from discovery.
- Test-only dependencies were not declared separately; `TestClient` tests require HTTPX.

`env/core` itself should not be repaired or downgraded because its interpreter is intentionally Python 3.11.

## Workaround / Fix

Add repository-level `pytest.ini`:

```ini
[pytest]
testpaths = tests
norecursedirs =
    env
    runtime
    workspace
    gui/node_modules
    .git
    .pytest_cache
```

Add `requirements-dev.txt`:

```text
pytest>=7,<9
httpx>=0.27,<1
```

Install test-only packages in the developer interpreter used to launch pytest:

```powershell
python -m pip install --user -r requirements-dev.txt
```

Then run:

```powershell
python -m pytest -q
```

## Regression guard

- Root `pytest` must collect only `tests/`.
- `env/`, `runtime/`, `workspace/`, and frontend dependency trees must never be test collection roots.
- GUI API tests must have a declared HTTP client dependency.

## Verification

Package-level verification performed when creating this hotfix:

- synthetic root pytest test confirms `testpaths=tests` ignores a deliberately failing file under `env/core`;
- hotfix ZIP contains no runtime, environment, workspace, or recording data.

Real Windows full-suite verification remains required after installation.

## Risks / Trade-offs

`requirements-dev.txt` is intentionally separate from production environment recipes. It is only for development/test execution and does not change the runtime dependency surface of `env/core`, `env/seg`, or `env/gui`.

## Removal condition

The hotfix can be replaced if Videoto3D later introduces a dedicated reproducible test environment or a unified project-level dependency manager. The root discovery exclusions should remain conceptually equivalent.

## Timeline

- 2026-08-17 — V1.3 focused tests passed 9/9.
- 2026-08-17 — Root pytest discovery entered `env/core`; root cause confirmed.
- 2026-08-17 — Explicit `tests/` run exposed missing HTTPX test dependency.
- 2026-08-17 — V1.3.0 Hotfix 1 prepared.
