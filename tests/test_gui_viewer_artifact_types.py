from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ViewerArtifactTypeTests(unittest.TestCase):
    def test_generic_viewer_supports_normal_ply_without_videoto3d_concepts(self):
        text = (ROOT / 'gui/viewer/src/AssetViewer.tsx').read_text(encoding='utf-8')
        self.assertIn('PLYLoader', text)
        self.assertIn("'pointcloud'", text)
        self.assertIn("'mesh-ply'", text)
        for forbidden in ('run_id', 'COLMAP', 'OpenMVS', 'workspace/runs', '/api/runs/'):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
