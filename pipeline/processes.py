"""Cross-platform detached GUI process helpers."""

import os
import subprocess

# Windows creation flags are stable Win32 constants. getattr keeps this module
# importable on non-Windows test hosts where subprocess omits them.
_DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


def detached_popen_kwargs(platform=None):
    platform = platform or ("windows" if os.name == "nt" else "posix")
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if platform == "windows":
        kwargs["creationflags"] = _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return kwargs


def launch_detached(command, cwd=None, platform=None):
    kwargs = detached_popen_kwargs(platform=platform)
    return subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        **kwargs,
    )
