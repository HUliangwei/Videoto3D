from pathlib import Path


def test_trackball_keys_disable_value_is_fixed_length_tuple_literal():
    source = (Path(__file__).resolve().parents[1] / 'gui' / 'viewer' / 'src' / 'AssetViewer.tsx').read_text(encoding='utf-8')
    assert "controls.keys = ['', '', '']" in source
    assert 'controls.keys = []' not in source
