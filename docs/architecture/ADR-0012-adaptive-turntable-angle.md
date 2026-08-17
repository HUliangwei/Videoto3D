# ADR-0012 — Turntable uses adaptive per-frame angular increments

- **Status:** Accepted
- **Date:** 2026-08-17
- **Version:** V1.3.2

## Context

V1.3.1 fixed the Turntable camera path but assigned equal angular increments to equal frame-time increments. Real handheld/manual rotation can change speed, making those known poses geometrically inconsistent with the images.

## Decision

Keep the one-axis/full-turn model, but estimate each adjacent angular increment from COLMAP's already verified two-view epipolar geometry. Robustly smooth these magnitudes and normalize the total to one turn. Fall back to uniform angles only when verified adjacent-pair coverage is insufficient.

## Consequences

- User does not need a constant rotation speed.
- No OpenCV/SciPy dependency is added.
- Orbit Camera and both reconstruction routes remain unchanged.
- Long direction reversals and non-rigid subjects remain outside this model.
