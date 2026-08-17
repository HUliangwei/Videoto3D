import json
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gui.control.server.artifacts import (
    build_artifact_catalog,
    colmap_model_as_ply,
    read_ply_counts,
    resolve_sequence_item,
)


def write_points3d(path, points):
    """Write the small subset of COLMAP points3D.bin needed by the test."""
    header = struct.Struct('<Q3d3BdQ')
    track = struct.Struct('<II')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as handle:
        handle.write(struct.pack('<Q', len(points)))
        for pid, xyz, rgb in points:
            handle.write(header.pack(pid, *xyz, *rgb, 0.2, 1))
            handle.write(track.pack(1, 0))


def write_ply(path, vertices, faces=None):
    faces = faces or 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        'ply\nformat ascii 1.0\n'
        f'element vertex {vertices}\nproperty float x\nproperty float y\nproperty float z\n'
        f'element face {faces}\nproperty list uchar int vertex_indices\nend_header\n',
        encoding='ascii',
    )


class ArtifactCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = self.root / 'workspace' / 'runs' / 'demo_001'
        for name in ('frames','masks','colmap','mesh/openmvs','splat/dataset/sparse/0','splat/raw','output'):
            (self.run / name).mkdir(parents=True, exist_ok=True)
        manifest = {
            'schema_version': 4,
            'run_id': 'demo_001',
            'shared': {s: {'status': 'ready'} for s in ('extract','mask','sparse')},
            'routes': {
                'mesh': {s: {'status': 'ready'} for s in ('dense','reconstruct','refine','texture','glb')},
                'splat': {
                    'training': {'status': 'ready', 'raw_path': 'splat/raw/demo_001_raw.ply'},
                    'cleanup': {'status': 'ready'},
                    'ply': {'status': 'ready', 'path': 'output/demo_001_splat.ply'},
                },
            },
        }
        manifest['routes']['mesh']['glb']['path'] = 'output/demo_001.glb'
        (self.run / 'run.json').write_text(json.dumps(manifest), encoding='utf-8')
        for i in range(1, 4):
            (self.run / 'frames' / f'frame_{i:04d}.jpg').write_bytes(b'jpg' + bytes([i]))
        for i in range(1, 3):
            (self.run / 'masks' / f'frame_{i:04d}.jpg.png').write_bytes(b'png' + bytes([i]))
        write_points3d(self.run / 'colmap/sparse/0/points3D.bin', [
            (1, (0.0, 0.0, 0.0), (255, 0, 0)),
            (2, (1.0, 2.0, 3.0), (0, 255, 0)),
        ])
        write_points3d(self.run / 'splat/dataset/sparse/0/points3D.bin', [
            (2, (1.0, 2.0, 3.0), (0, 255, 0)),
        ])
        write_ply(self.run / 'mesh/openmvs/scene_dense.ply', 900)
        write_ply(self.run / 'mesh/openmvs/scene_mesh.ply', 120, 220)
        write_ply(self.run / 'mesh/openmvs/scene_refined.ply', 100, 180)
        (self.run / 'mesh/openmvs/object_material_0_map_Kd.jpg').write_bytes(b'texture')
        write_ply(self.run / 'splat/raw/demo_001_raw.ply', 500)
        write_ply(self.run / 'output/demo_001_splat.ply', 350)
        (self.run / 'output/demo_001.glb').write_bytes(b'glTF')

    def tearDown(self):
        self.tmp.cleanup()

    def by_key(self, catalog):
        return {item['key']: item for group in catalog['groups'] for item in group['artifacts']}

    def test_catalog_exposes_every_pipeline_artifact_and_partial_masks(self):
        items = self.by_key(build_artifact_catalog(self.root, 'demo_001'))
        self.assertEqual(set(items), {
            'frames','masks','sparse','camera-trajectory','dense','raw-mesh','refined-mesh','textures','glb',
            'object-sparse','raw-splat','clean-splat',
        })
        self.assertEqual(items['frames']['state'], 'ready')
        self.assertEqual(items['frames']['count'], 3)
        self.assertEqual(items['masks']['state'], 'partial')
        self.assertEqual(items['masks']['count'], 2)
        self.assertEqual(items['sparse']['metrics']['points'], 2)
        self.assertEqual(items['camera-trajectory']['state'], 'missing')
        self.assertEqual(items['dense']['metrics']['vertices'], 900)
        self.assertEqual(items['raw-mesh']['metrics']['faces'], 220)
        self.assertEqual(items['textures']['count'], 1)
        self.assertEqual(items['raw-splat']['metrics']['vertices'], 500)
        self.assertEqual(items['clean-splat']['metrics']['vertices'], 350)

    def test_ready_manifest_with_missing_file_is_reported_missing(self):
        (self.run / 'mesh/openmvs/scene_refined.ply').unlink()
        items = self.by_key(build_artifact_catalog(self.root, 'demo_001'))
        self.assertEqual(items['refined-mesh']['state'], 'missing')

    def test_sequence_resolution_is_fixed_to_run_artifact_and_range_checked(self):
        first = resolve_sequence_item(self.root, 'demo_001', 'frames', 0)
        self.assertEqual(first.name, 'frame_0001.jpg')
        with self.assertRaises(IndexError):
            resolve_sequence_item(self.root, 'demo_001', 'frames', 99)
        with self.assertRaises(ValueError):
            resolve_sequence_item(self.root, 'demo_001', '../frames', 0)

    def test_colmap_sparse_is_exported_as_browser_ply_with_rgb(self):
        payload = colmap_model_as_ply(self.run / 'colmap/sparse/0')
        self.assertTrue(payload.startswith(b'ply\nformat binary_little_endian 1.0\n'))
        self.assertIn(b'element vertex 2\n', payload[:300])
        self.assertIn(b'property uchar red\n', payload[:300])

    def test_ply_header_counts_are_read_without_loading_whole_file(self):
        self.assertEqual(read_ply_counts(self.run / 'mesh/openmvs/scene_mesh.ply'), {'vertices': 120, 'faces': 220})


if __name__ == '__main__':
    unittest.main()
