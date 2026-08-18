import subprocess, sys
from pathlib import Path
from pipeline.run_lock import run_resource_lock
from pipeline.viewer_snapshot import snapshot_viewer_asset

def test_run_resource_lock_rejects_second_process(tmp_path):
    run_root=tmp_path/"run"; run_root.mkdir()
    repo_root=Path(__file__).resolve().parents[1]
    child=(
        "from pipeline.run_lock import run_resource_lock,RunResourceBusyError;"
        "from pathlib import Path;import sys;root=Path(sys.argv[1]);"
        "\ntry:\n"
        "    with run_resource_lock(root,'splat'):\n"
        "        print('acquired')\n"
        "except RunResourceBusyError:\n"
        "    print('busy')\n"
        "    raise SystemExit(17)\n"
    )
    with run_resource_lock(run_root,"splat"):
        result=subprocess.run([sys.executable,"-c",child,str(run_root)],cwd=str(repo_root),
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    assert result.returncode==17
    assert "busy" in result.stdout

def test_viewer_snapshot_is_independent(tmp_path):
    source=tmp_path/"chair_raw.ply"; source.write_bytes(b"ply\nexample\n")
    snapshot=snapshot_viewer_asset(source,working_dir=tmp_path)
    assert snapshot!=source and snapshot.read_bytes()==source.read_bytes()
    source.unlink()
    assert snapshot.exists()

def test_source_contract_uses_lock_and_snapshot():
    root=Path(__file__).resolve().parents[1]
    assert 'with run_resource_lock(run_root, "splat"):' in (root/"app.py").read_text(encoding="utf-8")
    assert "snapshot_viewer_asset" in (root/"pipeline"/"brush.py").read_text(encoding="utf-8")
