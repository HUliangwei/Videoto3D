from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendArtifactContractTests(unittest.TestCase):
    def test_capture_workflow_views_mount_pipeline_artifact_inspector(self):
        base = ROOT / "gui" / "control" / "web" / "src" / "workflows"
        for rel in (
            "orbit-camera/OrbitCameraRunView.tsx",
            "turntable/TurntableRunView.tsx",
        ):
            text = (base / rel).read_text(encoding="utf-8")
            self.assertIn("import { ArtifactInspector }", text)
            self.assertIn("<ArtifactInspector runId={id}", text)
            self.assertLess(
                text.index("<ArtifactInspector runId={id}"),
                text.index("RESULT VIEWER"),
            )

    def test_artifact_inspector_has_learning_and_ab_preview_controls(self):
        text = (ROOT / 'gui/control/web/src/components/ArtifactInspector.tsx').read_text(encoding='utf-8')
        self.assertIn('PIPELINE ARTIFACTS', text)
        self.assertIn('Original', text)
        self.assertIn('Overlay', text)
        self.assertIn('Raw Splat', text)
        self.assertIn('Clean Splat', text)
        self.assertIn('<AssetViewer', text)

    def test_api_and_types_expose_artifact_catalog(self):
        api = (ROOT / 'gui/control/web/src/api.ts').read_text(encoding='utf-8')
        types = (ROOT / 'gui/control/web/src/types.ts').read_text(encoding='utf-8')
        self.assertIn('artifacts:', api)
        self.assertIn('ArtifactCatalog', types)
        self.assertIn("'pointcloud'", types)
        self.assertIn("'mesh-ply'", types)


if __name__ == '__main__':
    unittest.main()
