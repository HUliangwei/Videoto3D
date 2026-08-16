"""Background process jobs for the Videoto3D local GUI control layer."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from pipeline.env_manager import environment_python
from pipeline.run_workspace import create_or_load_run, validate_run_id
from gui.control.server.progress import build_progress_snapshot


TERMINAL = {"succeeded", "failed", "cancelled"}


class JobConflictError(RuntimeError):
    pass


class JobNotFoundError(KeyError):
    pass


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JobManager:
    def __init__(self, project_root, max_lines=2500, popen_factory=subprocess.Popen):
        self.root = Path(project_root).resolve()
        self.max_lines = int(max_lines)
        self.popen_factory = popen_factory
        self._lock = threading.RLock()
        self._jobs = {}

    def _public(self, job):
        with self._lock:
            lines = list(job["lines"])
            run_root = self.root / "workspace" / "runs" / job["run_id"]
            progress = build_progress_snapshot(
                run_root=run_root,
                kind=job["kind"],
                command=job["command"],
                lines=lines,
                status=job["status"],
            )
            return {
                "job_id": job["job_id"],
                "run_id": job["run_id"],
                "kind": job["kind"],
                "status": job["status"],
                "command": list(job["command"]),
                "started_at": job["started_at"],
                "finished_at": job.get("finished_at"),
                "returncode": job.get("returncode"),
                "log_path": str(job["log_path"]),
                "lines": lines,
                "progress": progress,
            }

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(str(job_id))
            if job is None:
                raise JobNotFoundError(str(job_id))
            return self._public(job)

    def active_for_run(self, run_id):
        run_id = validate_run_id(run_id)
        with self._lock:
            return any(j["run_id"] == run_id and j["status"] not in TERMINAL for j in self._jobs.values())

    def active_jobs(self):
        with self._lock:
            return [self._public(j) for j in self._jobs.values() if j["status"] not in TERMINAL]

    def start_core(self, run_id, kind, app_args):
        python = environment_python(self.root, "core")
        command = [str(python), "-u", str(self.root / "app.py"), *[str(x) for x in app_args]]
        return self.start_command(run_id, kind, command)

    def start_command(self, run_id, kind, command):
        run_id = validate_run_id(run_id)
        if not command:
            raise ValueError("Job command cannot be empty")
        with self._lock:
            if self.active_for_run(run_id):
                raise JobConflictError("Run {} already has an active GUI job".format(run_id))
            run_root, _ = create_or_load_run(self.root / "workspace" / "runs", run_id)
            log_dir = run_root / "logs" / "gui"
            log_dir.mkdir(parents=True, exist_ok=True)
            job_id = uuid.uuid4().hex[:12]
            log_path = log_dir / (job_id + ".log")
            env = os.environ.copy()
            env["PYTHONNOUSERSITE"] = "1"
            kwargs = {
                "cwd": str(self.root),
                "env": env,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                kwargs["start_new_session"] = True
            process = self.popen_factory([str(x) for x in command], **kwargs)
            job = {
                "job_id": job_id,
                "run_id": run_id,
                "kind": str(kind),
                "status": "running",
                "command": [str(x) for x in command],
                "started_at": _now(),
                "finished_at": None,
                "returncode": None,
                "log_path": log_path,
                "lines": deque(maxlen=self.max_lines),
                "process": process,
                "cancel_requested": False,
            }
            self._jobs[job_id] = job
        threading.Thread(target=self._capture, args=(job_id,), daemon=True).start()
        return self._public(job)

    def _capture(self, job_id):
        with self._lock:
            job = self._jobs[job_id]
            process = job["process"]
            log_path = job["log_path"]
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            stream = process.stdout
            if stream is not None:
                for line in stream:
                    text = line.rstrip("\r\n")
                    log.write(text + "\n")
                    log.flush()
                    with self._lock:
                        job["lines"].append(text)
        code = process.wait()
        with self._lock:
            job["returncode"] = int(code)
            job["finished_at"] = _now()
            if job["cancel_requested"]:
                job["status"] = "cancelled"
            else:
                job["status"] = "succeeded" if code == 0 else "failed"

    def cancel(self, job_id):
        with self._lock:
            job = self._jobs.get(str(job_id))
            if job is None:
                raise JobNotFoundError(str(job_id))
            if job["status"] in TERMINAL:
                return self._public(job)
            job["cancel_requested"] = True
            process = job["process"]
        try:
            if os.name == "nt" and hasattr(signal, "CTRL_BREAK_EVENT"):
                process.send_signal(signal.CTRL_BREAK_EVENT)
            elif os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
        return self.get(job_id)

    def cancel_all(self):
        for job in self.active_jobs():
            try:
                self.cancel(job["job_id"])
            except Exception:
                pass
