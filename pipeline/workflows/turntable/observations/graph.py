"""Observation-graph helpers for Turntable R0.3a."""
from __future__ import annotations

import re


def edge_schedule(frame_count, gaps):
    frame_count = int(frame_count)
    if frame_count < 2:
        raise ValueError("frame_count must be >= 2")

    normalized = sorted(set(int(gap) for gap in gaps))
    if not normalized or any(gap <= 0 for gap in normalized):
        raise ValueError("gaps must contain positive integers")

    edges = []
    for gap in normalized:
        if gap >= frame_count:
            continue
        if gap == 5:
            edges.extend(
                (left, left + gap)
                for left in range(0, frame_count - gap, gap)
            )
        else:
            edges.extend(
                (left, left + gap)
                for left in range(frame_count - gap)
            )
    return edges


def _raw_count_from_exception(exc):
    match = re.search(
        r"Too few masked feature matches:\s*(\d+)",
        str(exc),
    )
    return int(match.group(1)) if match else 0


def build_observation_graph(
    frame_count,
    gaps,
    match_pair,
    min_correspondences=8,
):
    min_correspondences = int(min_correspondences)
    if min_correspondences < 8:
        raise ValueError("min_correspondences must be >= 8")

    accepted = []
    rejected = []
    counts = {}

    for left_index, right_index in edge_schedule(frame_count, gaps):
        gap = int(right_index - left_index)
        stats = counts.setdefault(
            gap,
            {"attempted": 0, "accepted": 0, "rejected": 0},
        )
        stats["attempted"] += 1

        try:
            matched = match_pair(left_index, right_index)
            raw_count = int(matched.get("match_count", 0))
        except RuntimeError as exc:
            raw_count = _raw_count_from_exception(exc)
            rejected.append(
                {
                    "left_index": int(left_index),
                    "right_index": int(right_index),
                    "gap": gap,
                    "raw_match_count": raw_count,
                    "reason": (
                        "too_few_correspondences"
                        if "Too few masked feature matches" in str(exc)
                        else "match_failed"
                    ),
                    "error": str(exc),
                }
            )
            stats["rejected"] += 1
            continue

        if raw_count < min_correspondences:
            rejected.append(
                {
                    "left_index": int(left_index),
                    "right_index": int(right_index),
                    "gap": gap,
                    "raw_match_count": raw_count,
                    "reason": "too_few_correspondences",
                }
            )
            stats["rejected"] += 1
            continue

        accepted.append(
            {
                "left_index": int(left_index),
                "right_index": int(right_index),
                "gap": gap,
                "left_points_px": matched["left_points_px"],
                "right_points_px": matched["right_points_px"],
                "feature_method": matched.get("method", "UNKNOWN"),
                "raw_match_count": raw_count,
            }
        )
        stats["accepted"] += 1

    return {
        "frame_count": int(frame_count),
        "gaps": [int(g) for g in sorted(set(int(g) for g in gaps))],
        "accepted_edges": accepted,
        "rejected_edges": rejected,
        "counts_by_gap": counts,
        "attempted_edge_count": int(len(accepted) + len(rejected)),
        "accepted_edge_count": int(len(accepted)),
        "rejected_edge_count": int(len(rejected)),
    }
