"""Runtime validation and launcher for Videoto3D Studio."""

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
import urllib.request
from pathlib import Path

from pipeline.env_manager import ensure_environment, environment_python
from gui.control.server.frontend import ensure_frontend


GUI_VERSION = "1.3.3.2"
DEFAULT_GUI_PORT = 8765
MAX_PORT_PROBES = 20


def gui_python_path(project_root):
    return environment_python(project_root, "gui")


def gui_runtime_status(project_root):
    root = Path(project_root)
    dist_index = root / "gui" / "control" / "web" / "dist" / "index.html"
    if not dist_index.exists():
        return False, "GUI 前端尚未构建；python app.py gui 会自动执行 npm install + npm run build"
    return True, "Videoto3D Studio runtime ready"


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def _gui_url(host, port):
    return "http://{}:{}".format(host, int(port))


def _probe_gui_health(project_root, host, port, timeout=0.45):
    """Return the existing Studio URL only when the port serves this project."""
    url = _gui_url(host, port)
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=float(timeout)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if payload.get("status") != "ready":
        return None
    existing_root = payload.get("project_root")
    if not existing_root or not _same_path(existing_root, project_root):
        return None
    return url


def _port_is_available(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _select_gui_target(project_root, host, preferred_port):
    """Return (port, existing_url). Reuse same-project Studio, otherwise find a free port."""
    preferred_port = int(preferred_port)
    existing = _probe_gui_health(project_root, host, preferred_port)
    if existing:
        return preferred_port, existing
    if _port_is_available(host, preferred_port):
        return preferred_port, None
    for candidate in range(preferred_port + 1, preferred_port + MAX_PORT_PROBES + 1):
        existing = _probe_gui_health(project_root, host, candidate)
        if existing:
            return candidate, existing
        if _port_is_available(host, candidate):
            return candidate, None
    raise RuntimeError(
        "No free Videoto3D Studio port found in {}-{}.".format(
            preferred_port, preferred_port + MAX_PORT_PROBES
        )
    )


def _request_gui_shutdown(endpoint):
    request = urllib.request.Request(endpoint, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=2.0) as response:
        response.read()


def _wait_for_gui_process(process, url, shutdown_request=_request_gui_shutdown):
    try:
        return int(process.wait())
    except KeyboardInterrupt:
        print("\n[GUI][STOP] Ctrl+C received; requesting graceful Studio shutdown...")
        try:
            shutdown_request(url + "/api/system/shutdown?force=1")
        except Exception as exc:
            print("[GUI][WARN] graceful shutdown request failed: {}".format(exc))
            try:
                process.terminate()
            except Exception:
                pass
        try:
            return int(process.wait(timeout=8))
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
            return int(process.wait())


def _print_reuse(url):
    print("=" * 68)
    print("Videoto3D Studio V{}".format(GUI_VERSION))
    print("URL     :", url + "/")
    print("Mode    : reuse existing Studio instance")
    print("Status  : [READY] existing server belongs to this project")
    print("=" * 68)


def _serve_gui(project_root, host="127.0.0.1", port=DEFAULT_GUI_PORT, open_browser=True, strict_port=False):
    import uvicorn
    from gui.control.server.app import create_app

    root = Path(project_root)
    ensure_frontend(root)

    if not strict_port:
        port, existing_url = _select_gui_target(root, host, port)
        if existing_url:
            _print_reuse(existing_url)
            if open_browser:
                webbrowser.open(existing_url + "/")
            return 0

    shutdown_event = threading.Event()
    app = create_app(project_root=root, shutdown_event=shutdown_event)
    config = uvicorn.Config(app, host=host, port=int(port), log_level="info")
    server = uvicorn.Server(config)

    def watch_shutdown():
        shutdown_event.wait()
        server.should_exit = True

    threading.Thread(target=watch_shutdown, daemon=True).start()
    url = _gui_url(host, port)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url + "/")).start()
    print("=" * 68)
    print("Videoto3D Studio V{}".format(GUI_VERSION))
    print("URL     :", url + "/")
    print("Mode    : local control Studio + reusable Web viewer")
    print("Stop    : 网页 Exit Studio（推荐）或 Ctrl+C")
    print("=" * 68)
    server.run()
    return 0


def run_gui_server(project_root, host="127.0.0.1", port=DEFAULT_GUI_PORT, open_browser=True):
    root = Path(project_root)
    gui_python = ensure_environment(root, "gui")
    ensure_frontend(root)

    selected_port, existing_url = _select_gui_target(root, host, port)
    if existing_url:
        _print_reuse(existing_url)
        if open_browser:
            webbrowser.open(existing_url + "/")
        return 0

    if selected_port != int(port):
        print("[GUI][WARN] port {} is busy; using {} instead.".format(port, selected_port))

    if _same_path(sys.executable, gui_python):
        return _serve_gui(
            root,
            host=host,
            port=selected_port,
            open_browser=open_browser,
            strict_port=True,
        )

    command = [
        str(gui_python), "-m", "gui.control.server.launcher",
        "--serve", str(root), "--host", host, "--port", str(selected_port), "--strict-port",
    ]
    if not open_browser:
        command.append("--no-browser")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(command, cwd=str(root), creationflags=creationflags)
    return _wait_for_gui_process(process, _gui_url(host, selected_port))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", dest="project_root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_GUI_PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--strict-port", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.project_root:
        parser.error("--serve <project_root> is required")
    return _serve_gui(
        args.project_root,
        args.host,
        args.port,
        not args.no_browser,
        strict_port=args.strict_port,
    )


if __name__ == "__main__":
    raise SystemExit(main())
