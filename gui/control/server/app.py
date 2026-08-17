"""FastAPI application for the Videoto3D V1.3.0 local control Studio."""

import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gui.control.server.artifacts import (
    build_artifact_catalog,
    colmap_model_as_ply,
    colmap_camera_centers_as_ply,
    resolve_artifact_file,
    resolve_colmap_model,
    resolve_sequence_item,
)
from gui.control.server.jobs import JobConflictError, JobManager, JobNotFoundError
from pipeline.capture_mode import normalize_capture_mode
from gui.control.server.service import (
    get_run_detail,
    list_runs,
    prepare_uploaded_source,
    resolve_first_frame,
    resolve_run_asset,
)


def default_project_root():
    return Path(__file__).resolve().parents[3]


def default_static_dir(project_root=None):
    root = Path(project_root or default_project_root())
    return root / "gui" / "control" / "web" / "dist"


def _box_from_payload(payload):
    box = payload.get("box") if isinstance(payload, dict) else None
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("box must be [x0,y0,x1,y1]")
    try:
        values = tuple(int(x) for x in box)
    except (TypeError, ValueError):
        raise ValueError("box must contain four integers")
    x0, y0, x1, y1 = values
    if min(values) < 0 or x1 <= x0 or y1 <= y0:
        raise ValueError("box must satisfy 0<=x0<x1 and 0<=y0<y1")
    return values


SPLAT_OPTIONS = (
    "steps", "max_splats", "max_resolution",
    "foreground_ratio", "min_foreground_observations",
    "cleanup_ratio", "cleanup_min_views",
)

MESH_OPTIONS = (
    "undistort_max_image_size",
    "dense_resolution_level",
    "dense_number_views",
    "dense_max_threads",
    "refine_resolution_level",
)


def _mesh_args(run_id, payload):
    payload = payload if isinstance(payload, dict) else {}
    unknown = set(payload) - set(MESH_OPTIONS)
    if unknown:
        raise ValueError("Unknown Mesh options: {}".format(", ".join(sorted(unknown))))
    args = ["route", "mesh", "--run", run_id]
    for key in MESH_OPTIONS:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError("{} must be an integer".format(key))
        if key == "undistort_max_image_size" and number <= 0:
            raise ValueError("undistort_max_image_size must be > 0")
        if key != "undistort_max_image_size" and number < 0:
            raise ValueError("{} must be >= 0".format(key))
        args.extend(["--" + key.replace("_", "-"), str(number)])
    return args


def _splat_args(run_id, payload):
    payload = payload if isinstance(payload, dict) else {}
    unknown = set(payload) - set(SPLAT_OPTIONS)
    if unknown:
        raise ValueError("Unknown Splat options: {}".format(", ".join(sorted(unknown))))
    args = ["route", "splat", "--run", run_id]
    for key in SPLAT_OPTIONS:
        value = payload.get(key)
        if value is not None and value != "":
            args.extend(["--" + key.replace("_", "-"), str(value)])
    return args


def _image_media(path):
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def create_app(project_root=None, static_dir=None, shutdown_event=None, job_manager=None):
    project_root = Path(project_root or default_project_root()).resolve()
    if static_dir is None:
        static_dir = default_static_dir(project_root)
    static_dir = Path(static_dir).resolve() if static_dir else None
    jobs = job_manager or JobManager(project_root)

    app = FastAPI(title="Videoto3D Studio", version="1.3.0")
    app.state.project_root = project_root
    app.state.jobs = jobs

    @app.get("/api/health")
    def health():
        return {"status": "ready", "project_root": str(project_root), "version": "1.3.0"}

    @app.get("/api/runs")
    def runs():
        return list_runs(project_root)

    @app.post("/api/system/shutdown")
    def shutdown(force: bool = False):
        active = jobs.active_jobs()
        if active and not force:
            raise HTTPException(status_code=409, detail="Control jobs are still running; cancel or wait before Exit Studio")
        if active and force:
            jobs.cancel_all()
        if shutdown_event is None:
            raise HTTPException(status_code=409, detail="Shutdown is unavailable for this server instance")
        shutdown_event.set()
        return {"status": "stopping"}

    @app.post("/api/runs/{run_id}/source")
    async def upload_source(run_id: str, filename: str, request: Request, capture_mode: str = "orbit_camera"):
        try:
            capture_mode = normalize_capture_mode(capture_mode)
            path = prepare_uploaded_source(project_root, run_id, filename)
            with path.open("wb") as output:
                async for chunk in request.stream():
                    output.write(chunk)
            if path.stat().st_size <= 0:
                path.unlink(missing_ok=True)
                raise ValueError("Uploaded source is empty")
            job = jobs.start_core(
                run_id, "extract",
                ["run", "extract", "--run", run_id, "--input", str(path), "--capture-mode", capture_mode],
            )
            return {"run_id": run_id, "source": str(path), "job": job}
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/runs/{run_id}/frames/first")
    def first_frame(run_id: str):
        try:
            return FileResponse(resolve_first_frame(project_root, run_id), media_type="image/jpeg")
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/runs/{run_id}/mask")
    async def run_mask(run_id: str, request: Request):
        try:
            resolve_first_frame(project_root, run_id)
            values = _box_from_payload(await request.json())
            box = ",".join(str(x) for x in values)
            return jobs.start_core(run_id, "mask", ["run", "mask", "--run", run_id, "--box", box])
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/runs/{run_id}/route/mesh")
    async def route_mesh(run_id: str, request: Request):
        try:
            detail = get_run_detail(project_root, run_id)
            if detail.get("shared", {}).get("mask", {}).get("status") != "ready":
                raise HTTPException(status_code=409, detail="SAM2 mask is not ready; select the subject first")
            raw = await request.body()
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            return jobs.start_core(run_id, "mesh", _mesh_args(run_id, payload))
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/runs/{run_id}/route/splat")
    async def route_splat(run_id: str, request: Request):
        try:
            detail = get_run_detail(project_root, run_id)
            if detail.get("shared", {}).get("mask", {}).get("status") != "ready":
                raise HTTPException(status_code=409, detail="SAM2 mask is not ready; select the subject first")
            payload = await request.json()
            return jobs.start_core(run_id, "splat", _splat_args(run_id, payload))
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/runs/{run_id}/job")
    def active_run_job(run_id: str):
        try:
            run_id = str(run_id)
            for item in jobs.active_jobs():
                if item.get("run_id") == run_id:
                    return item
            return None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        try:
            return jobs.get(job_id)
        except (JobNotFoundError, KeyError):
            raise HTTPException(status_code=404, detail="Unknown job")

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        try:
            return jobs.cancel(job_id)
        except (JobNotFoundError, KeyError):
            raise HTTPException(status_code=404, detail="Unknown job")

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str):
        try:
            return get_run_detail(project_root, run_id)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # V1.2.0 read-only Pipeline Artifact Inspector API.
    @app.get("/api/runs/{run_id}/artifacts")
    def artifacts(run_id: str):
        try:
            return build_artifact_catalog(project_root, run_id)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/runs/{run_id}/artifacts/frames/{index}")
    def artifact_frame(run_id: str, index: int):
        try:
            path = resolve_sequence_item(project_root, run_id, "frames", index)
            return FileResponse(path, media_type=_image_media(path), filename=path.name)
        except (FileNotFoundError, ValueError, RuntimeError, IndexError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/runs/{run_id}/artifacts/masks/{index}")
    def artifact_mask(run_id: str, index: int):
        try:
            path = resolve_sequence_item(project_root, run_id, "masks", index)
            return FileResponse(path, media_type=_image_media(path), filename=path.name)
        except (FileNotFoundError, ValueError, RuntimeError, IndexError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/runs/{run_id}/artifacts/textures/{index}")
    def artifact_texture(run_id: str, index: int):
        try:
            path = resolve_sequence_item(project_root, run_id, "textures", index)
            return FileResponse(path, media_type=_image_media(path), filename=path.name)
        except (FileNotFoundError, ValueError, RuntimeError, IndexError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/runs/{run_id}/artifacts/file/{key}")
    def artifact_file(run_id: str, key: str):
        try:
            if key in ("sparse", "object-sparse", "camera-trajectory"):
                model = resolve_colmap_model(project_root, run_id, key)
                payload = (
                    colmap_camera_centers_as_ply(model)
                    if key == "camera-trajectory" else colmap_model_as_ply(model)
                )
                return Response(
                    content=payload,
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": 'inline; filename="{}.ply"'.format(key)},
                )
            path = resolve_artifact_file(project_root, run_id, key)
            media = "model/gltf-binary" if key == "glb" else "application/octet-stream"
            return FileResponse(path, media_type=media, filename=path.name)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/runs/{run_id}/assets/{kind}")
    def asset(run_id: str, kind: str):
        if kind not in ("glb", "splat"):
            raise HTTPException(status_code=404, detail="Unknown asset kind")
        try:
            path = resolve_run_asset(project_root, run_id, kind)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        media = "model/gltf-binary" if kind == "glb" else "application/octet-stream"
        return FileResponse(path, media_type=media, filename=path.name)

    if static_dir and (static_dir / "index.html").exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = (static_dir / full_path).resolve()
            try:
                candidate.relative_to(static_dir)
            except ValueError:
                candidate = static_dir / "index.html"
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
