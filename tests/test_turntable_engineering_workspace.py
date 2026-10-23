import json
from pathlib import Path

from pipeline.workflows.turntable.engineering import (
    assert_run_local_path,
    update_turntable_stage,
)


def test_run_local_path_rejects_escape(tmp_path):
    root = tmp_path / "workspace" / "runs" / "chair"
    root.mkdir(parents=True)
    assert assert_run_local_path(root, root / "turntable" / "anchor.json") == root / "turntable" / "anchor.json"
    try:
        assert_run_local_path(root, tmp_path / "outside.json")
    except RuntimeError as exc:
        assert "outside Run workspace" in str(exc)
    else:
        raise AssertionError("path escape was accepted")


def test_turntable_stage_state_is_written_inside_run_json(tmp_path):
    root = tmp_path / "workspace" / "runs" / "chair"
    root.mkdir(parents=True)
    (root / "run.json").write_text(
        json.dumps({"run_id":"chair","capture_mode":"turntable"}),
        encoding="utf-8",
    )
    update_turntable_stage(root, "anchor", "ready", path="turntable/anchor.json")
    manifest = json.loads((root / "run.json").read_text(encoding="utf-8"))
    assert manifest["turntable"]["anchor"]["status"] == "ready"
    assert manifest["turntable"]["anchor"]["path"] == "turntable/anchor.json"
