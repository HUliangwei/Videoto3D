import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import threading

from fastapi.testclient import TestClient

from gui.control.server.app import create_app


class FakeJobs:
    def __init__(self):
        self.started = []
        self.jobs = {}
        self.cancelled = []
    def start_core(self, run_id, kind, args):
        job = {"job_id": "job{}".format(len(self.started)+1), "run_id": run_id, "kind": kind, "status": "running", "lines": []}
        self.started.append((run_id, kind, list(args)))
        self.jobs[job["job_id"]] = job
        return job
    def get(self, job_id):
        if job_id not in self.jobs: raise KeyError(job_id)
        return self.jobs[job_id]
    def cancel(self, job_id):
        self.cancelled.append(job_id); self.jobs[job_id]["status"] = "cancelled"; return self.jobs[job_id]
    def active_jobs(self):
        return [j for j in self.jobs.values() if j["status"] == "running"]
    def cancel_all(self):
        for jid in list(self.jobs): self.cancel(jid)


class GuiApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        run_root = self.root / "workspace" / "runs" / "demo_001"
        (run_root / "output").mkdir(parents=True)
        (run_root / "quality").mkdir(parents=True)
        manifest = {
            "schema_version": 4,
            "videoto3d_version": "0.11",
            "run_id": "demo_001",
            "created_at": "2026-08-17T00:00:00+00:00",
            "updated_at": "2026-08-17T00:10:00+00:00",
            "source": {},
            "shared": {s: {"status": "ready"} for s in ("extract", "mask", "sparse")},
            "routes": {
                "mesh": {s: {"status": "ready"} for s in ("dense", "reconstruct", "refine", "texture", "glb")},
                "splat": {s: {"status": "ready"} for s in ("training", "cleanup", "ply")},
            },
        }
        manifest["routes"]["mesh"]["glb"]["path"] = "output/demo_001.glb"
        manifest["routes"]["splat"]["ply"]["path"] = "output/demo_001_splat.ply"
        (run_root / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run_root / "quality" / "report.json").write_text(json.dumps({"run_id": "demo_001"}), encoding="utf-8")
        (run_root / "output" / "demo_001.glb").write_bytes(b"glTF")
        (run_root / "output" / "demo_001_splat.ply").write_bytes(b"ply\n")
        self.jobs = FakeJobs()
        self.client = TestClient(create_app(project_root=self.root, static_dir=None, job_manager=self.jobs))

    def tearDown(self):
        self.tmp.cleanup()

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ready")

    def test_runs_and_detail(self):
        r = self.client.get("/api/runs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0]["run_id"], "demo_001")
        d = self.client.get("/api/runs/demo_001")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.json()["assets"]["glb"], "/api/runs/demo_001/assets/glb")

    def test_asset_stream(self):
        r = self.client.get("/api/runs/demo_001/assets/splat")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ply\n")

    def test_unknown_run_is_404(self):
        self.assertEqual(self.client.get("/api/runs/missing_001").status_code, 404)

    def test_explicit_shutdown_sets_event(self):
        event = threading.Event()
        client = TestClient(create_app(project_root=self.root, static_dir=None, shutdown_event=event))
        response = client.post("/api/system/shutdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "stopping")
        self.assertTrue(event.is_set())

    def test_new_run_source_upload_streams_inside_run_and_starts_extract(self):
        response = self.client.post(
            "/api/runs/new_001/source?filename=clip.mp4",
            content=b"video-bytes",
            headers={"content-type": "application/octet-stream"},
        )
        self.assertEqual(response.status_code, 200)
        source = self.root / "workspace" / "runs" / "new_001" / "source" / "clip.mp4"
        self.assertEqual(source.read_bytes(), b"video-bytes")
        self.assertEqual(self.jobs.started[-1][0:2], ("new_001", "extract"))
        args = self.jobs.started[-1][2]
        self.assertEqual(args[:4], ["run", "extract", "--run", "new_001"])
        self.assertIn(str(source), args)

    def test_source_upload_rejects_path_filename(self):
        response = self.client.post("/api/runs/new_001/source?filename=../clip.mp4", content=b"x")
        self.assertEqual(response.status_code, 400)

    def test_first_frame_mask_and_route_controls_use_existing_core_cli(self):
        run_root = self.root / "workspace" / "runs" / "demo_001"
        (run_root / "frames").mkdir(exist_ok=True)
        (run_root / "frames" / "frame_0001.jpg").write_bytes(b"jpeg")
        first = self.client.get("/api/runs/demo_001/frames/first")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, b"jpeg")

        mask = self.client.post("/api/runs/demo_001/mask", json={"box": [10, 20, 300, 400]})
        self.assertEqual(mask.status_code, 200)
        self.assertEqual(self.jobs.started[-1][2], ["run", "mask", "--run", "demo_001", "--box", "10,20,300,400"])

        mesh = self.client.post("/api/runs/demo_001/route/mesh")
        self.assertEqual(mesh.status_code, 200)
        self.assertEqual(self.jobs.started[-1][2], ["route", "mesh", "--run", "demo_001"])

        splat = self.client.post("/api/runs/demo_001/route/splat", json={"steps": 10000, "cleanup_ratio": 0.8})
        self.assertEqual(splat.status_code, 200)
        args = self.jobs.started[-1][2]
        self.assertEqual(args[:4], ["route", "splat", "--run", "demo_001"])
        self.assertIn("--steps", args); self.assertIn("10000", args)
        self.assertIn("--cleanup-ratio", args); self.assertIn("0.8", args)

    def test_job_status_cancel_and_shutdown_busy_guard(self):
        self.jobs.jobs["abc"] = {"job_id": "abc", "run_id": "demo_001", "kind": "mesh", "status": "running", "lines": ["hello"]}
        status = self.client.get("/api/jobs/abc")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["lines"], ["hello"])
        busy = self.client.post("/api/system/shutdown")
        self.assertEqual(busy.status_code, 409)
        cancel = self.client.post("/api/jobs/abc/cancel")
        self.assertEqual(cancel.status_code, 200)

    def test_built_spa_is_served_with_history_fallback(self):
        static_dir = self.root / "dist"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>studio</html>", encoding="utf-8")
        client = TestClient(create_app(project_root=self.root, static_dir=static_dir))
        self.assertIn("studio", client.get("/").text)
        self.assertIn("studio", client.get("/runs/teddy_001").text)


if __name__ == "__main__":
    unittest.main()

class GuiV112ApiTests(GuiApiTests):
    def test_mesh_route_accepts_settings_json(self):
        response = self.client.post("/api/runs/demo_001/route/mesh", json={
            "undistort_max_image_size": 1600,
            "dense_resolution_level": 1,
            "dense_number_views": 6,
            "dense_max_threads": 4,
            "refine_resolution_level": 2,
        })
        self.assertEqual(response.status_code, 200)
        args = self.jobs.started[-1][2]
        self.assertIn("--undistort-max-image-size", args)
        self.assertIn("1600", args)
        self.assertIn("--dense-number-views", args)
        self.assertIn("6", args)

    def test_run_detail_exposes_read_only_paths_and_runtime(self):
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config" / "tools.json").write_text(json.dumps({"tools": {"colmap": {"path": "C:/COLMAP/COLMAP.bat", "source": "saved"}}}), encoding="utf-8")
        response = self.client.get("/api/runs/demo_001")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("paths", body)
        self.assertIn("project", body["paths"])
        self.assertIn("environments", body["paths"])
        self.assertIn("tools", body["paths"])
        self.assertIn("run", body["paths"])
        self.assertEqual(body["paths"]["tools"]["colmap"]["path"], "C:/COLMAP/COLMAP.bat")
