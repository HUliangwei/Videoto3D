import numpy as np

from pipeline.workflows.turntable.observations.graph import (
    build_observation_graph,
    edge_schedule,
)


def test_edge_schedule_gap_1_2_3_and_sparse_5():
    edges = edge_schedule(12, (1, 2, 3, 5))
    assert (0, 1) in edges
    assert (0, 2) in edges
    assert (0, 3) in edges
    assert (0, 5) in edges
    assert (5, 10) in edges
    assert (1, 6) not in edges


def test_graph_rejects_edges_with_fewer_than_8_matches():
    def fake_match(i, j):
        count = 12 if (i, j) == (0, 1) else 6
        points = np.zeros((count, 2), dtype=np.float64)
        return {
            "left_points_px": points,
            "right_points_px": points.copy(),
            "method": "TEST",
            "match_count": count,
        }

    graph = build_observation_graph(
        frame_count=3,
        gaps=(1,),
        match_pair=fake_match,
        min_correspondences=8,
    )
    assert len(graph["accepted_edges"]) == 1
    assert len(graph["rejected_edges"]) == 1
    assert graph["rejected_edges"][0]["reason"] == "too_few_correspondences"
    assert graph["counts_by_gap"][1]["accepted"] == 1
    assert graph["counts_by_gap"][1]["rejected"] == 1
