import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from gui.control.server.jobs import JobConflictError, JobManager


def wait_done(manager, job_id, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        job = manager.get(job_id)
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.03)
    raise AssertionError("job did not finish")


def test_job_manager_captures_stdout_and_persists_log():
    with TemporaryDirectory() as td:
        root = Path(td)
        manager = JobManager(root)
        started = manager.start_command(
            "demo_001", "test",
            [sys.executable, "-u", "-c", "print('hello-control')"],
        )
        job = wait_done(manager, started["job_id"])
        assert job["status"] == "succeeded"
        assert any("hello-control" in line for line in job["lines"])
        assert Path(job["log_path"]).read_text(encoding="utf-8").strip() == "hello-control"


def test_job_manager_allows_only_one_active_job_per_run():
    with TemporaryDirectory() as td:
        root = Path(td)
        manager = JobManager(root)
        first = manager.start_command(
            "demo_001", "slow",
            [sys.executable, "-u", "-c", "import time; print('start'); time.sleep(0.7)"],
        )
        with pytest.raises(JobConflictError):
            manager.start_command("demo_001", "second", [sys.executable, "-c", "print('x')"])
        wait_done(manager, first["job_id"])
