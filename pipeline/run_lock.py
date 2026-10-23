"""Cross-process run resource locks for Videoto3D."""
from __future__ import annotations
import os
from contextlib import contextmanager
from pathlib import Path

class RunResourceBusyError(RuntimeError):
    pass

def _ensure_lock_byte(handle):
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)

def _read_owner(handle):
    try:
        handle.seek(1)
        text = handle.read().decode("ascii", errors="ignore").strip()
        return text or "unknown"
    except Exception:
        return "unknown"

def _write_owner(handle):
    handle.seek(1)
    handle.truncate()
    handle.write(("pid={}".format(os.getpid())).encode("ascii"))
    handle.flush()

def _acquire(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

def _release(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

@contextmanager
def run_resource_lock(run_root, resource):
    run_root = Path(run_root).resolve()
    resource = str(resource).strip().lower()
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    if not resource or any(ch not in allowed for ch in resource):
        raise ValueError("Invalid run resource name: {!r}".format(resource))
    lock_dir = run_root / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / (resource + ".lock")
    handle = lock_path.open("a+b")
    _ensure_lock_byte(handle)
    try:
        try:
            _acquire(handle)
        except OSError as exc:
            raise RunResourceBusyError(
                "Run resource {!r} is busy for {} ({}). Wait for the other CLI/GUI job to finish before retrying."
                .format(resource, run_root.name, _read_owner(handle))
            ) from exc
        _write_owner(handle)
        yield lock_path
    finally:
        try:
            _release(handle)
        except Exception:
            pass
        handle.close()
