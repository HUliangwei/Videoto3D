"""Runtime validation and launcher for Videoto3D Studio."""

import argparse
import importlib.util
import os
import subprocess
import sys
import threading
import webbrowser
import urllib.request
from pathlib import Path

from pipeline.env_manager import ensure_environment, environment_python
from gui.control.server.frontend import ensure_frontend


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


def _serve_gui(project_root, host="127.0.0.1", port=8765, open_browser=True):
    import uvicorn
    from gui.control.server.app import create_app

    root = Path(project_root)
    ensure_frontend(root)
    shutdown_event = threading.Event()
    app = create_app(project_root=root, shutdown_event=shutdown_event)
    config = uvicorn.Config(app, host=host, port=int(port), log_level="info")
    server = uvicorn.Server(config)

    def watch_shutdown():
        shutdown_event.wait()
        server.should_exit = True

    threading.Thread(target=watch_shutdown, daemon=True).start()
    url = "http://{}:{}/".format(host, port)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print("=" * 68)
    print("Videoto3D Studio V1.1.2")
    print("URL     :", url)
    print("Mode    : local control Studio + reusable Web viewer")
    print("Stop    : 网页 Exit Studio（推荐）或 Ctrl+C")
    print("=" * 68)
    server.run()
    return 0


def run_gui_server(project_root, host="127.0.0.1", port=8765, open_browser=True):
    root = Path(project_root)
    gui_python = ensure_environment(root, "gui")
    ensure_frontend(root)
    if _same_path(sys.executable, gui_python):
        return _serve_gui(root, host=host, port=port, open_browser=open_browser)
    command = [str(gui_python), "-m", "gui.control.server.launcher", "--serve", str(root), "--host", host, "--port", str(port)]
    if not open_browser:
        command.append("--no-browser")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(command, cwd=str(root), creationflags=creationflags)
    return _wait_for_gui_process(process, "http://{}:{}".format(host, port))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", dest="project_root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not args.project_root:
        parser.error("--serve <project_root> is required")
    return _serve_gui(args.project_root, args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
