# Turntable R0.2a Structured Essential Research

R0.1 passed the 60-frame nonuniform free-span synthetic benchmark.

R0.2a removes ground-truth angle from estimator input but deliberately keeps
ground-truth shared geometry (axis + orbit vector). This isolates the
structured essential model before shared-geometry estimation.

Paper-grounded premise: Kosaka et al., *Turntable-Constrained Camera Pose
Estimation* (CVPRW 2026) states that single-axis sequences share a rotation
axis, translation is induced by rotation of a shared orbit vector, and the
essential matrices form a low-dimensional structured family.

Official source:
`https://openaccess.thecvf.com/content/CVPR2026W/IMW/html/Kosaka_Turntable-Constrained_Camera_Pose_Estimation_CVPRW_2026_paper.html`

Videoto3D R0.2a convention:

```text
R_ij = R(a, delta_theta_ij)
t_ij = v - R_ij v
E_ij = [t_ij]_x R_ij
```

This exact sign/coordinate convention is a Videoto3D implementation convention
pending line-by-line audit of the full paper PDF equations.

Do not promote to triangulation yet.
