# BUG-0007 · Core environment missing Pillow

- **Status:** Resolved
- **Severity:** High
- **Affected:** Videoto3D V1.1.1 project-local `env/core`
- **Resolved in:** V1.1.2

## Symptom

Mesh Route reached OpenMVS preparation and stopped before Dense with:

```text
[ERROR] Mask validation requires Pillow in the main Python environment.
Install it with: python -m pip install pillow
```

The command was already running from `D:\Desktop\Videoto3D\env\core\python.exe`, so installing Pillow into another Conda environment did not solve the project-local Core dependency gap.

## Root cause

`pipeline.segmentation.validate_masks()` uses Pillow, but `config/envs/core.yml` contained Python, pip and NumPy only. The Core environment health probe also tested only NumPy, so a recipe-created Core could be marked READY while lacking a runtime dependency required by Mesh mask validation.

## Fix

V1.1.2 adds Pillow to the Core Conda recipe and changes the Core environment validation probe to import `PIL.Image` as well as NumPy.

## Regression guard

`tests/test_env_manager.py` verifies both the recipe entry and the PIL health probe.

## Removal condition

Permanent project dependency; do not remove while Core-side mask validation uses Pillow.
