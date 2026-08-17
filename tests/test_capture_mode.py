from pathlib import Path

import pytest

from pipeline.capture_mode import (
    DEFAULT_CAPTURE_MODE,
    capture_mode_label,
    is_turntable,
    normalize_capture_mode,
    sparse_mask_path,
)
from pipeline.cli_commands import parse_cli_args
from pipeline.colmap import build_feature_extractor_args
from pipeline.run_workspace import (
    create_or_load_run,
    load_run_manifest,
    update_capture_mode,
)


def test_capture_mode_normalization_and_labels():
    assert normalize_capture_mode(None) == DEFAULT_CAPTURE_MODE
    assert normalize_capture_mode("orbit-camera") == "orbit_camera"
    assert normalize_capture_mode("turn_table") == "turntable"
    assert capture_mode_label("turntable") == "Turntable"
    assert is_turntable("turntable") is True
    assert is_turntable("orbit_camera") is False
    with pytest.raises(ValueError):
        normalize_capture_mode("dynamic_human")


def test_turntable_sparse_uses_sam2_mask_directory(tmp_path):
    assert sparse_mask_path(tmp_path, "orbit_camera") is None
    assert sparse_mask_path(tmp_path, "turntable") == tmp_path / "masks"

    args = build_feature_extractor_args(
        database_path=tmp_path / "database.db",
        image_path=tmp_path / "frames",
        mask_path=tmp_path / "masks",
    )
    index = args.index("--ImageReader.mask_path")
    assert Path(args[index + 1]) == tmp_path / "masks"


def test_run_manifest_defaults_to_orbit_and_can_store_turntable(tmp_path):
    run_root, manifest = create_or_load_run(tmp_path, "turntable_001")
    assert manifest["capture_mode"] == "orbit_camera"
    update_capture_mode(run_root, "turntable")
    assert load_run_manifest(run_root)["capture_mode"] == "turntable"


def test_cli_accepts_capture_mode_only_at_capture_entry_points():
    parsed = parse_cli_args([
        "run", "extract", "--run", "demo", "--input", "demo.mp4",
        "--capture-mode", "turntable",
    ])
    assert parsed["kind"] == "command"
    assert parsed["options"]["capture_mode"] == "turntable"

    route = parse_cli_args([
        "route", "mesh", "--run", "demo", "--capture-mode", "orbit-camera",
    ])
    assert route["kind"] == "command"
    assert route["options"]["capture_mode"] == "orbit_camera"

    rejected = parse_cli_args([
        "run", "sparse", "--run", "demo", "--capture-mode", "turntable",
    ])
    assert rejected["kind"] == "error"
