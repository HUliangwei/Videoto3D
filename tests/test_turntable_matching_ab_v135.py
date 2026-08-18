import sqlite3
from pathlib import Path

import pytest

from tools.turntable_matching_ab_v135 import (
    benchmark_paths,
    clone_database_for_exhaustive,
    compare_matching_results,
    database_match_stats,
    exhaustive_matcher_args,
)


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB)")
    con.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)")
    con.execute("CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
    con.execute("CREATE TABLE descriptors (image_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
    con.execute("CREATE TABLE matches (pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
    con.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, config INTEGER, F BLOB, E BLOB, H BLOB, qvec BLOB, tvec BLOB)")
    con.execute("INSERT INTO cameras VALUES (1,2,720,1280,?)", (b"camera",))
    con.execute("INSERT INTO images VALUES (1,'frame_0001.jpg',1)")
    con.execute("INSERT INTO images VALUES (2,'frame_0002.jpg',1)")
    con.execute("INSERT INTO keypoints VALUES (1,4,2,?)", (b"kp1",))
    con.execute("INSERT INTO keypoints VALUES (2,5,2,?)", (b"kp2",))
    con.execute("INSERT INTO descriptors VALUES (1,4,128,?)", (b"d1",))
    con.execute("INSERT INTO descriptors VALUES (2,5,128,?)", (b"d2",))
    con.execute("INSERT INTO matches VALUES (2147483649,7,2,?)", (b"matches",))
    con.execute("INSERT INTO two_view_geometries VALUES (2147483649,6,2,?,2,NULL,NULL,NULL,NULL,NULL)", (b"verified",))
    con.commit()
    con.close()


def test_benchmark_paths_never_point_at_shared_sparse(tmp_path):
    run_root = tmp_path / "workspace" / "runs" / "hlw_04"
    paths = benchmark_paths(run_root)

    assert paths["root"] == run_root / "colmap" / "diagnostics" / "matching_ab_v135"
    assert paths["exhaustive_database"] == paths["exhaustive"] / "database.db"
    assert run_root / "colmap" / "sparse" / "0" not in paths.values()
    assert run_root / "colmap" / "database.db" not in paths.values()


def test_clone_database_preserves_features_but_clears_old_matches(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "copy" / "database.db"
    _make_db(source)

    clone_database_for_exhaustive(source, destination)

    source_con = sqlite3.connect(source)
    dest_con = sqlite3.connect(destination)
    try:
        assert source_con.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
        assert source_con.execute("SELECT COUNT(*) FROM two_view_geometries").fetchone()[0] == 1
        assert dest_con.execute("SELECT COUNT(*) FROM keypoints").fetchone()[0] == 2
        assert dest_con.execute("SELECT COUNT(*) FROM descriptors").fetchone()[0] == 2
        assert dest_con.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0
        assert dest_con.execute("SELECT COUNT(*) FROM two_view_geometries").fetchone()[0] == 0
    finally:
        source_con.close()
        dest_con.close()


def test_database_match_stats_counts_verified_pairs_and_inliers(tmp_path):
    database = tmp_path / "database.db"
    _make_db(database)

    stats = database_match_stats(database)

    assert stats["raw_match_pairs"] == 1
    assert stats["raw_matches"] == 7
    assert stats["verified_pairs"] == 1
    assert stats["verified_inliers"] == 6


def test_exhaustive_matcher_args_reuse_existing_features_and_enable_guided_gpu():
    args = exhaustive_matcher_args(Path("diagnostics/database.db"))

    assert args[0] == "exhaustive_matcher"
    assert "--database_path" in args
    assert "--FeatureMatching.guided_matching" in args
    assert args[args.index("--FeatureMatching.guided_matching") + 1] == "1"
    assert args[args.index("--FeatureMatching.use_gpu") + 1] == "1"
    assert "feature_extractor" not in args


def test_compare_matching_results_reports_sparse_and_coverage_deltas():
    sequential = {
        "matching": {"verified_pairs": 54, "verified_inliers": 6400},
        "pose": {"constraint_count": 30, "gap_coverage_ratio": 0.54, "adjacent_coverage_ratio": 0.54, "span_deg": 395.8},
        "selected_stats": {"points3D": 2076, "mean_track_length": 2.463, "mean_reprojection_error": 1.467},
    }
    exhaustive = {
        "matching": {"verified_pairs": 310, "verified_inliers": 24200},
        "pose": {"constraint_count": 61, "gap_coverage_ratio": 0.86, "adjacent_coverage_ratio": 0.81, "span_deg": 331.2},
        "selected_stats": {"points3D": 3020, "mean_track_length": 3.11, "mean_reprojection_error": 1.49},
    }

    comparison = compare_matching_results(sequential, exhaustive)

    assert comparison["verified_pairs_delta"] == 256
    assert comparison["constraint_count_delta"] == 31
    assert comparison["gap_coverage_ratio_delta"] == pytest.approx(0.32)
    assert comparison["points3D_delta"] == 944
    assert comparison["points3D_ratio"] == pytest.approx(3020 / 2076)
    assert comparison["mean_track_length_delta"] == pytest.approx(0.647)
    assert comparison["mean_reprojection_error_delta"] == pytest.approx(0.023)
    assert comparison["exhaustive_improves_coverage"] is True
    assert comparison["exhaustive_improves_track_length"] is True
