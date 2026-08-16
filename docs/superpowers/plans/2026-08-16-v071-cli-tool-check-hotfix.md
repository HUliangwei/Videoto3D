# Videoto3D V0.7.1 CLI Tool Check Hotfix

## Root cause
V0.7 canonical CLI `main()` routes reconstruction/view commands through `check_required_tools(required_tools_for_key(key))`, but the V0.7 packaging/refactor omitted the `check_required_tools()` definition that existed in the V0.6 baseline. Any canonical command requiring COLMAP/OpenMVS/Blender therefore failed with `NameError` before tool validation.

## Fix
Restore `check_required_tools(tool_names)` as the command-scoped environment validator. It resolves only the tools required by the selected canonical command and returns `(ok, resolved)` without changing the V0.7 CLI surface or workspace routing.

## Regression coverage
`tests/test_doctor.py::TestDoctorConfigAndCommandScope::test_check_required_tools_resolves_requested_tool` fails on the broken V0.7 tree and passes after the restore. Full suite and CLI routing smoke tests must pass before packaging.

## README rule
No canonical commands changed. Root `README.md` is still updated with a V0.7.1 hotfix note so every distributed ZIP records its behavior/version delta.
