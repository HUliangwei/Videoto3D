# BUG-0003 — Project-local Conda bootstrap rejects `-y` on `conda env create/update`

- **Status:** Resolved
- **Severity:** High
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** Videoto3D V1.0.1 project-local environment bootstrap
- **Fixed/Mitigated in:** V1.0.1 Hotfix 1
- **Upstream:** Not an upstream defect; Videoto3D passed an incompatible CLI flag

## Summary

V1.0.1 could fail before creating `env/core` because the environment manager appended `-y` to `conda env create` and `conda env update`. The user's installed Anaconda `conda-env-script.py` rejected that flag for `env create`, and `conda env update` does not expose a `-y/--yes` option in the documented CLI.

## Symptom

Running:

```text
python app.py gui
```

failed immediately with:

```text
[ENV][MISSING] core
[ENV][CREATE] core -> D:\Desktop\Videoto3D\env\core
conda-env-script.py: error: unrecognized arguments: -y
EnvironmentSetupError: Environment command failed (exit 2): ... conda.exe env create ... -y
```

## Reproduction

```text
1. Install Videoto3D V1.0.1 on a Windows machine whose conda-env CLI rejects -y.
2. Ensure env/core does not exist.
3. Run python app.py gui.
4. Bootstrap calls conda env create ... -y and exits with code 2.
```

## Evidence

The traceback identifies `pipeline/env_manager.py::ensure_environment()` as the source of the generated command. The pre-fix unit tests reproduced the generated command exactly:

```text
... conda.exe env create -p <prefix> -f <core.yml> -y
... conda.exe env update -p <prefix> -f <core.yml> --prune -y
```

Both new regression tests failed before the fix because `-y` was present.

## Root cause

The bootstrap assumed `-y` was a portable option for both `conda env create` and `conda env update`. That assumption is false across supported Conda installations. In particular, the user's installed `conda env create` parser rejected the option, while the documented `conda env update` interface does not define `-y`.

The existing tests only checked that the generated command contained `env create`, `-p`, and the target prefix. They did not guard the complete command against unsupported flags, so the compatibility defect passed unit tests.

## Workaround / Fix

Generate the portable commands without `-y`:

```text
conda env create -p <prefix> -f <recipe>
conda env update -p <prefix> -f <recipe> --prune
```

No Conda upgrade is required. If a failed V1.0.1 attempt left a partial `env/core`, the existing bootstrap already removes a prefix that does not contain `python.exe` before retrying creation.

## Regression guard

`tests/test_env_manager.py` now explicitly asserts that both create and update commands contain neither `-y` nor `--yes`.

## Verification

- Regression tests observed RED on V1.0.1 command construction.
- Removing the unsupported flags made both tests GREEN.
- Full project regression and fresh-overlay verification are required before shipping the hotfix ZIP.

## Risks / Trade-offs

The fix intentionally relies on `conda env create/update`'s normal non-interactive environment-file workflow rather than forcing a confirmation flag that is not portable across Conda versions.

## Removal condition

This is a permanent compatibility fix. Do not reintroduce `-y/--yes` for `conda env update`; any future prompt-control strategy must first be compatibility-tested against the minimum supported Conda version.

## Timeline

- 2026-08-17 — Detected from first real V1.0.1 project-local core bootstrap.
- 2026-08-17 — Root cause confirmed in command construction and official Conda CLI references.
- 2026-08-17 — Regression tests added and minimal fix implemented.
