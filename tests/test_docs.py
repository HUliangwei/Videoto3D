import unittest
from pathlib import Path


class TestProjectDocs(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_bug_registry_contains_template_and_openmvs_240_incident(self):
        bugs = self.root / "docs" / "bugs"
        self.assertTrue((bugs / "README.md").exists())
        self.assertTrue((bugs / "_TEMPLATE.md").exists())
        self.assertTrue((bugs / "BUG-0001-openmvs-2.4.0-texture-black-artifacts.md").exists())

    def test_openmvs_bug_record_documents_workaround_and_upstream(self):
        incident = (
            self.root / "docs" / "bugs" /
            "BUG-0001-openmvs-2.4.0-texture-black-artifacts.md"
        ).read_text(encoding="utf-8")
        self.assertIn("--global-seam-leveling 0", incident)
        self.assertIn("--local-seam-leveling 0", incident)
        self.assertIn("https://github.com/cdcseacave/openMVS/issues/1251", incident)
        self.assertIn("Types.inl", incident)

    def test_readme_points_to_bug_registry_and_current_openmvs_mask_name(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/bugs", readme)
        self.assertIn("frame_0001.mask.png", readme)
        self.assertNotIn("frame_0001.jpg.mask.png", readme)

    def test_v08_docs_describe_multi_run_and_blender_glb_preview(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("workspace/runs/<run_id>/", readme)
        self.assertIn("python app.py runs list", readme)
        self.assertIn("python app.py view glb (--run <run_id> | --path <glb>)", readme)
        guide = self.root / "docs" / "troubleshooting" / "blender-glb-viewing.md"
        self.assertTrue(guide.exists())
        if guide.exists():
            text = guide.read_text(encoding="utf-8")
            self.assertIn("Material Preview", text)
            self.assertIn("blender.exe file.glb", text)

    def test_v09_docs_describe_brush_splat_and_detached_viewers(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("python app.py run splat --run <run_id>", readme)
        self.assertIn("python app.py view splat", readme)
        self.assertIn("SPLAT", readme)
        bug = root / "docs" / "bugs" / "BUG-0002-viewer-process-does-not-release-terminal.md"
        self.assertTrue(bug.exists())
        adr = root / "docs" / "architecture" / "ADR-0002-gaussian-splat-branch.md"
        self.assertTrue(adr.exists())


if __name__ == "__main__":
    unittest.main()

class TestV10Docs(unittest.TestCase):
    def test_v10_docs_describe_flat_dual_routes_and_object_sparse(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        adr = Path("docs/architecture/ADR-0003-dual-route-flat-run-layout.md").read_text(encoding="utf-8")
        self.assertIn("python app.py route mesh --run <run_id>", readme)
        self.assertIn("python app.py route splat --run <run_id>", readme)
        self.assertIn("python app.py view splat-init --run <run_id>", readme)
        self.assertIn("object_sparse_report.json", readme)
        self.assertIn("Shared + Mesh/Splat Route", adr)

class TestV11Docs(unittest.TestCase):
    def test_v11_docs_describe_cleanup_quality_and_raw_final_split(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        adr = Path("docs/architecture/ADR-0004-post-brush-splat-cleanup.md").read_text(encoding="utf-8")
        self.assertIn("python app.py quality --run <run_id>", readme)
        self.assertIn("--cleanup-ratio 0.7", readme)
        self.assertIn("splat/raw/<run_id>_raw.ply", readme)
        self.assertIn("quality/report.json", readme)
        self.assertIn("Post-Brush Splat Cleanup", adr)
        self.assertIn("Changing only cleanup thresholds must not retrain Brush", adr)

class TestV100Docs(unittest.TestCase):
    def test_v100_docs_define_gui_control_viewer_boundary(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        gui = Path("gui/README.md").read_text(encoding="utf-8")
        adr = Path("docs/architecture/ADR-0005-gui-control-viewer-boundary.md").read_text(encoding="utf-8")
        self.assertIn("python app.py gui", readme)
        self.assertIn("gui/control", readme)
        self.assertIn("gui/viewer", readme)
        self.assertIn("must **not** know about Videoto3D", gui)
        self.assertIn("type + src", adr)
