import json
from pathlib import Path
import unittest


class GuiFrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_viewer_source_has_no_videoto3d_control_concepts(self):
        src = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (self.root / "gui" / "viewer" / "src").glob("*.ts*")
        ).lower()
        for forbidden in ("workspace/runs", "/api/runs", "run_id", "colmap", "openmvs"):
            self.assertNotIn(forbidden, src)

    def test_viewer_public_api_is_type_and_src(self):
        text = (self.root / "gui" / "viewer" / "src" / "AssetViewer.tsx").read_text(encoding="utf-8")
        self.assertIn("type: AssetType", text)
        self.assertIn("src: string", text)
        self.assertIn("type === 'glb'", text)
        self.assertIn("new SplatMesh", text)

    def test_control_web_consumes_reusable_viewer_package(self):
        package = json.loads((self.root / "gui" / "control" / "web" / "package.json").read_text(encoding="utf-8"))
        self.assertIn("@videoto3d/viewer", package["dependencies"])
        base = self.root / "gui" / "control" / "web" / "src" / "workflows"
        workflow_views = "\n".join(
            (base / rel).read_text(encoding="utf-8")
            for rel in (
                "orbit-camera/OrbitCameraRunView.tsx",
                "turntable/TurntableRunView.tsx",
            )
        )
        self.assertIn("from '@videoto3d/viewer'", workflow_views)

    def test_v110_server_controls_runs_through_core_jobs(self):
        text = (self.root / "gui" / "control" / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.post("/api/runs/{run_id}/source")', text)
        self.assertIn('@app.post("/api/runs/{run_id}/mask")', text)
        self.assertIn('@app.post("/api/runs/{run_id}/route/mesh")', text)
        self.assertIn('@app.post("/api/runs/{run_id}/route/splat")', text)
        self.assertIn('jobs.start_core', text)
        self.assertNotIn("beforeunload", text.lower())
        self.assertNotIn("@app.delete", text)

    def test_viewer_has_reusable_navigation_controls(self):
        text = (self.root / "gui" / "viewer" / "src" / "AssetViewer.tsx").read_text(encoding="utf-8")
        for label in ("Fit", "Reset", "Front", "Back", "Left", "Right", "Top", "Bottom", "Iso", "Auto Rotate", "Fullscreen"):
            self.assertIn(label, text)
        self.assertIn("dblclick", text.lower())
        self.assertIn("TrackballControls", text)
        self.assertNotIn("OrbitControls", text)
        for label in ("Roll Left", "Flip", "Roll Right"):
            self.assertIn(label, text)

    def test_control_web_has_new_run_roi_routes_and_live_job_console(self):
        src = "\n".join(path.read_text(encoding="utf-8") for path in (self.root / "gui" / "control" / "web" / "src").rglob("*.tsx"))
        api = (self.root / "gui" / "control" / "web" / "src" / "api.ts").read_text(encoding="utf-8")
        for label in ("New Run", "Generate Masks", "Run Mesh", "Run Splat", "Cancel Job"):
            self.assertIn(label, src)
        self.assertIn("/frames/first", src)
        self.assertIn("route/mesh", api)
        self.assertIn("route/splat", api)
        self.assertIn("/api/jobs/", api)

    def test_control_web_has_explicit_exit_studio_without_unload_shutdown(self):
        app = (self.root / "gui" / "control" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
        api = (self.root / "gui" / "control" / "web" / "src" / "api.ts").read_text(encoding="utf-8")
        self.assertIn("Exit Studio", app)
        self.assertIn("shutdown", api)
        self.assertNotIn("beforeunload", app.lower())
        self.assertNotIn("pagehide", app.lower())


if __name__ == "__main__":
    unittest.main()

class V112FrontendContract(unittest.TestCase):
    def test_mesh_settings_and_path_inspector_are_visible_control_features(self):
        root = Path(__file__).resolve().parents[1]
        src = "\n".join(path.read_text(encoding="utf-8") for path in (root / "gui" / "control" / "web" / "src").rglob("*.tsx"))
        types = (root / "gui" / "control" / "web" / "src" / "types.ts").read_text(encoding="utf-8")
        api = (root / "gui" / "control" / "web" / "src" / "api.ts").read_text(encoding="utf-8")
        for text in ("Mesh Settings", "Paths & Runtime", "Copy Path", "Seam leveling"):
            self.assertIn(text, src)
        self.assertIn("MeshSettings", types)
        self.assertIn("routeMesh", api)
