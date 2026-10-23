# Turntable R0.2a Structured Essential Angle Estimator Design

**Goal:** Estimate pairwise Turntable angle from image correspondences with shared axis/orbit fixed from synthetic GT.

Constraints: Orbit Camera and `legacy_v13` unchanged; no GLB/PLY production integration; R0.2a does not estimate shared axis/orbit.

Architecture: masked SIFT/ORB correspondences -> normalized points -> median Sampson residual over a one-dimensional structured essential family.
