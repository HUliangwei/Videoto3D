import math
import inspect
import numpy as np

from pipeline.workflows.turntable.pose.multibaseline import prepare_graph_edges
from pipeline.workflows.turntable.pose.multi_hypothesis import (
    generate_pair_hypotheses,
)
from pipeline.workflows.turntable.pose.shared_geometry import observable_transverse_orbit
from pipeline.workflows.turntable.pose.single_axis import axis_angle_rotation, normalize_axis


def _project(k, points):
    pixels = (k @ points.T).T
    return pixels[:, :2] / pixels[:, 2:3]


def _prepared_pair(angle_deg=17.35):
    rng = np.random.default_rng(7)
    k = np.array([[820.0,0.0,360.0],[0.0,815.0,360.0],[0.0,0.0,1.0]])
    axis = normalize_axis([0.2, 0.95, 0.23])
    transverse = observable_transverse_orbit(axis, [1.0,0.0,0.0])
    r = axis_angle_rotation(axis, math.radians(angle_deg))
    t = transverse - r @ transverse
    left3 = rng.uniform([-0.8,-0.7,3.2],[0.8,0.7,5.5],size=(140,3))
    right3 = (r @ left3.T).T + t
    raw = [{
        "left_index": 0,
        "right_index": 3,
        "gap": 3,
        "left_points_px": _project(k,left3),
        "right_points_px": _project(k,right3),
        "feature_method": "SYNTHETIC",
        "raw_match_count": 140,
    }]
    edge = prepare_graph_edges(raw, k, max_points=120)[0]
    return axis, transverse, edge


def test_pair_hypotheses_include_true_angle():
    axis, transverse, edge = _prepared_pair(17.35)
    result = generate_pair_hypotheses(
        edge, axis, transverse,
        min_angle_deg=0.25,
        max_angle_deg=40.0,
        coarse_step_deg=0.25,
        refine_step_deg=0.05,
        top_k=3,
        min_separation_deg=0.5,
        keep_ratio=1.0,
    )
    assert len(result["candidates"]) >= 1
    oracle = min(abs(c["angle_deg"] - 17.35) for c in result["candidates"])
    assert oracle <= 0.06
    residuals = [c["residual_px"] for c in result["candidates"]]
    assert residuals == sorted(residuals)


def test_pair_hypothesis_api_is_anchor_trajectory_independent():
    signature = inspect.signature(generate_pair_hypotheses)
    names = set(signature.parameters)
    assert "anchor_angle_deg" not in names
    assert "deltas_deg" not in names
    assert "theta_deg" not in names


def test_hypotheses_are_separated():
    axis, transverse, edge = _prepared_pair(9.4)
    result = generate_pair_hypotheses(
        edge, axis, transverse,
        min_angle_deg=0.25,
        max_angle_deg=30.0,
        coarse_step_deg=0.25,
        refine_step_deg=0.05,
        top_k=4,
        min_separation_deg=0.5,
        keep_ratio=1.0,
    )
    angles = [c["angle_deg"] for c in result["candidates"]]
    for i in range(len(angles)):
        for j in range(i + 1, len(angles)):
            assert abs(angles[i] - angles[j]) >= 0.5 - 1e-12
