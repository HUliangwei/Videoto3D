import json
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from gui.control.server.app import create_app


class FakeJobs:
    def active_jobs(self): return []
    def cancel_all(self): return None
    def start_core(self, *args, **kwargs): raise AssertionError('artifact API must not start reconstruction jobs')
    def get(self, job_id): raise KeyError(job_id)
    def cancel(self, job_id): raise KeyError(job_id)


def write_points3d(path):
    header = struct.Struct('<Q3d3BdQ')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as handle:
        handle.write(struct.pack('<Q', 1))
        handle.write(header.pack(1, 1.0, 2.0, 3.0, 10, 20, 30, 0.1, 0))


class ArtifactApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        run = self.root / 'workspace/runs/demo_001'
        (run / 'frames').mkdir(parents=True)
        (run / 'masks').mkdir()
        (run / 'colmap/sparse/0').mkdir(parents=True)
        (run / 'output').mkdir()
        (run / 'frames/frame_0001.jpg').write_bytes(b'jpeg')
        (run / 'masks/frame_0001.jpg.png').write_bytes(b'png')
        write_points3d(run / 'colmap/sparse/0/points3D.bin')
        manifest = {
            'schema_version': 4, 'videoto3d_version': '0.11', 'run_id': 'demo_001',
            'source': {},
            'shared': {s: {'status': 'ready'} for s in ('extract','mask','sparse')},
            'routes': {
                'mesh': {s: {'status': 'pending'} for s in ('dense','reconstruct','refine','texture','glb')},
                'splat': {s: {'status': 'pending'} for s in ('training','cleanup','ply')},
            },
        }
        (run / 'run.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.client = TestClient(create_app(project_root=self.root, static_dir=None, job_manager=FakeJobs()))

    def tearDown(self): self.tmp.cleanup()

    def test_catalog_is_read_only_and_reports_shared_artifacts(self):
        response = self.client.get('/api/runs/demo_001/artifacts')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['run_id'], 'demo_001')
        self.assertEqual(body['groups'][0]['artifacts'][0]['key'], 'frames')

    def test_sequence_and_sparse_preview_endpoints(self):
        frame = self.client.get('/api/runs/demo_001/artifacts/frames/0')
        self.assertEqual(frame.status_code, 200)
        self.assertEqual(frame.content, b'jpeg')
        sparse = self.client.get('/api/runs/demo_001/artifacts/file/sparse')
        self.assertEqual(sparse.status_code, 200)
        self.assertTrue(sparse.content.startswith(b'ply\nformat binary_little_endian 1.0\n'))

    def test_unknown_artifacts_never_accept_arbitrary_paths(self):
        self.assertEqual(self.client.get('/api/runs/demo_001/artifacts/file/../../run.json').status_code, 404)
        self.assertEqual(self.client.get('/api/runs/demo_001/artifacts/file/not-a-key').status_code, 404)
        self.assertEqual(self.client.get('/api/runs/demo_001/artifacts/frames/99').status_code, 404)


if __name__ == '__main__':
    unittest.main()
