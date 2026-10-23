def test_sparse_engineering_runs_all_turntable_stages_in_order(monkeypatch, tmp_path):
    import pipeline.workflows.turntable.engineering as eng

    calls = []
    monkeypatch.setattr(eng, "run_anchor_stage", lambda colmap, root, overwrite=True: calls.append("anchor"))
    monkeypatch.setattr(eng, "run_pairs_stage", lambda root: calls.append("pairs"))
    monkeypatch.setattr(eng, "run_orbit_stage", lambda root: calls.append("orbit"))
    expected = {"frame_count": 60, "database": tmp_path/"database.db", "model": tmp_path/"sparse", "stats": {}}
    def triangulate(colmap, root, overwrite=True):
        calls.append("triangulate")
        return expected
    monkeypatch.setattr(eng, "run_triangulate_stage", triangulate)

    result = eng.run_sparse_engineering("COLMAP.bat", tmp_path)
    assert calls == ["anchor", "pairs", "orbit", "triangulate"]
    assert result is expected
