# BUG-0002: Viewer process keeps terminal attached after GUI exit

- Status: Resolved
- Severity: Medium
- Affected: Videoto3D V0.8 and earlier viewer launch paths
- Fixed in: V0.9
- Date: 2026-08-16

## Symptom

`view mesh` / `view glb` could open Blender correctly, but after the user closed Blender the PowerShell session could still behave as if a child process owned the console; the user had to press `Ctrl+C` before continuing comfortably. COLMAP GUI had the same process-launch pattern.

## Reproduction

```text
python app.py view glb --run teddy_001
# close Blender
# terminal remains coupled to child console handles / requires Ctrl+C
```

## Root cause

GUI children were created with plain `subprocess.Popen` while inheriting the parent's standard handles and process group. On Windows, console-subsystem applications launched this way can remain coupled to the caller's console lifecycle even though Videoto3D itself does not call `wait()`.

## Fix

V0.9 centralizes GUI launch in `pipeline/processes.py`.

Windows viewer processes use:

- `DETACHED_PROCESS`
- `CREATE_NEW_PROCESS_GROUP`
- `stdin/stdout/stderr = DEVNULL`
- `close_fds = True`

POSIX uses `start_new_session=True` plus detached stdio.

Blender, COLMAP and Brush viewers all use the same helper.

## Regression guard

`tests/test_processes.py` verifies detached process options. Blender and COLMAP tests verify that viewer launch routes through the detached helper.

## Verification

Expected V0.9 behavior:

1. Run any `python app.py view ...` command.
2. CLI immediately returns after printing the viewer PID.
3. Close the viewer.
4. No `Ctrl+C` is needed to use the terminal again.

## Removal condition

Permanent behavior; do not remove unless the viewer process architecture is replaced entirely (for example by an in-browser viewer owned by the future Web GUI).
