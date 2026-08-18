"""Viewer-safe immutable snapshots for mutable reconstruction assets."""
from __future__ import annotations
import os
import shutil
import time
from pathlib import Path

def _prune(cache_dir, stem, suffix, keep):
    items = sorted(
        cache_dir.glob(stem + ".*" + suffix),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for path in items[int(keep):]:
        try:
            path.unlink()
        except OSError:
            pass

def snapshot_viewer_asset(source, working_dir=None, keep=8):
    source = Path(source).resolve()
    if not source.exists():
        raise FileNotFoundError("Viewer asset not found: {}".format(source))
    base = Path(working_dir).resolve() if working_dir else source.parent
    cache_dir = base / "viewer_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    token = "{}.{}".format(os.getpid(), time.time_ns())
    snapshot = cache_dir / ("{}.{}{}".format(source.stem, token, source.suffix))
    shutil.copy2(str(source), str(snapshot))
    _prune(cache_dir, source.stem, source.suffix, keep)
    return snapshot
