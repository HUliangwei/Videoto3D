# BUG-0006: GUI Ctrl+C does not reliably return the parent shell

- **Status:** Resolved
- **Severity:** Medium
- **Affected:** V1.0.1–V1.0.2 project-local GUI environment launcher
- **Fixed in:** V1.1

## Symptom
`Exit Studio` successfully stopped Uvicorn, but Ctrl+C was not a reliable lifecycle control when `env/core` waited on a separate `env/gui` Python child process.

## Root cause
The Core launcher used a blocking `subprocess.run()` for the GUI interpreter and had no explicit parent-side Ctrl+C policy. On Windows, console control delivery across the bootstrap/core/gui process chain is not a sufficiently clear ownership model for the Studio lifecycle.

## Fix
The Core launcher now starts GUI Python as a managed process group and owns the wait loop. Ctrl+C is caught by the Core parent, which POSTs the existing shutdown endpoint with `force=1`, waits for graceful Uvicorn exit, and terminates only as fallback. Browser `Exit Studio` remains the recommended normal path.

## Regression coverage
`tests/test_gui_cli.py::GuiLifecycleTests::test_ctrl_c_requests_child_shutdown_then_waits`.
