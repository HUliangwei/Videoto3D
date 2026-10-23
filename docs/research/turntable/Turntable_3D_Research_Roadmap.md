# Videoto3D Turntable 3D Reconstruction Research Roadmap

> Status: Active research after Videoto3D V1.4.0  
> Branch: `research/turntable-global-orbit`  
> Stable production baseline: Orbit Camera in `v1.4.0`  
> Research scope: camera fixed, rigid object rotating around one dominant axis

## 1. Research Objective

Videoto3D V1.4 separates the two physical capture geometries. Orbit Camera is the stable engineering workflow. Turntable is now an independent research workflow rather than a parameter variation of ordinary moving-camera SfM.

The research objective is:

> Recover a physically consistent single-axis motion model from Turntable video and use it to drive both geometry reconstruction and Gaussian reconstruction.

The long-term Videoto3D target is **free-span, non-uniform, primarily one-directional Turntable capture**. This is our research extension; it is not a claim that the cited papers already solve that exact acquisition model.

## 2. Primary Papers

### 2.1 Kosaka et al., 2026

**Turntable-Constrained Camera Pose Estimation**  
Norio Kosaka, Shinichi Higashino, Shuji Yamaguchi  
CVPR Workshops 2026.

Official page:

`https://openaccess.thecvf.com/content/CVPR2026W/IMW/html/Kosaka_Turntable-Constrained_Camera_Pose_Estimation_CVPRW_2026_paper.html`

Expected local PDF:

`docs/research/turntable/papers/Kosaka_2026_Turntable_Constrained_Camera_Pose_Estimation.pdf`

Paper-supported ideas used here:

- single-axis sequences form a low-dimensional motion family;
- views share a common rotation axis and differ primarily by per-view angle;
- unconstrained pairwise SfM can produce physically inconsistent trajectories;
- the essential matrix has a structured form in which translation is induced by rotation of a shared orbit vector;
- the paper studies axis-projected rotations, structured essential estimation, and global orbit refinement;
- evaluation includes synthetic sequences and a Blender-based Turntable dataset.

### 2.2 Kim et al., 2026

**RotGS: Rotation-Guided 3D Gaussian Splatting for Turntable Sequences without Structure-from-Motion**  
Kyumin Kim, Dohae Lee, Hanul Baek, In-Kwon Lee  
Computer Graphics Forum / Eurographics 2026.

Official page:

`https://diglib.eg.org/items/ee2836a3-f205-46d3-94e1-bf22178f211b`

DOI:

`https://doi.org/10.1111/cgf.70317`

Expected local PDF:

`docs/research/turntable/papers/Kim_2026_RotGS.pdf`

Paper-supported ideas used here:

- Turntable background removal can reduce reliable feature matches and destabilize SfM;
- RotGS avoids SfM and represents object motion using one global rotation axis;
- estimated rotation is applied directly to the Gaussian set;
- Gaussian motion produces rotation flow;
- rotation flow is aligned with optical flow for geometric supervision;
- uncertainty-to-detail flow scheduling stabilizes early optimization;
- the method is evaluated on synthetic and real Turntable data.

## 3. Paper-derived ideas vs Videoto3D extensions

### Directly paper-derived

1. Shared single rotation axis.
2. Structured low-dimensional relative geometry rather than unconstrained 6-DoF pair poses.
3. Global orbit refinement.
4. SfM-free Gaussian optimization using rotation flow and optical-flow supervision.

### Videoto3D research extensions

1. Free-span motion: no forced 360-degree total.
2. Non-uniform speed: per-frame angular increments may vary.
3. Primarily one-directional motion: reversal is outside the initial model.
4. Geometry and Gaussian routes may share observations but evolve independently.
5. Angle trajectory, axis confidence, cycle residual and observability become first-class research artifacts.

## 4. Research Stages

### R0.1 — Synthetic Ground-Truth Benchmark

Deliver deterministic profiles (`uniform_360`, `nonuniform_360`, `nonuniform_280`), a Blender fixed-camera renderer, exact GT metadata, and quantitative axis/angle metrics.

No production Turntable route or GLB/PLY downstream code changes.

### R0.2 — Structured Single-Axis Geometry

Generalize the hard-coded V1.3 Y-axis algebra to an arbitrary shared axis and orbit vector.

```text
shared axis a
shared orbit vector v
pair angle delta_theta_ij
        |
        v
R_ij = R(a, delta_theta_ij)
t_ij coupled to R_ij and v
        |
        v
structured E_ij
```

### R0.3 — Multi-Hypothesis Pair Estimation

Retain multiple candidate angles per verified image pair rather than one local minimum.

### R0.4 — Cycle-Consistent Global Orbit

Solve one sequence-wide trajectory using shared axis, direction consensus, pair observations, graph/cycle consistency and only weak smoothness.

Outputs: axis, orbit representation, theta[0..T-1], confidence, coverage, cycle residuals and observability.

### R0.5 — Geometry Route

Only after synthetic pose metrics become credible:

```text
global Turntable pose
→ known virtual-camera poses
→ COLMAP point triangulation
→ Sparse QA
→ OpenMVS
→ Blender
→ GLB
```

### R0.6 — RotGS Reproduction

Implement the published RotGS principles in an independent Turntable Gaussian route:

```text
masked frames + fixed camera + shared axis + Gaussian set
→ rotation-induced Gaussian motion
→ rotation flow <-> optical flow
→ RGB + flow supervision
→ Gaussian reconstruction
→ PLY
```

First reproduce the paper-native method as faithfully as the downloaded PDF supports.

### R0.7 — Videoto3D Free-Span / Non-Uniform Gaussian Extension

Only after the paper baseline exists, replace or augment its angle trajectory with the globally initialized Videoto3D trajectory.

A candidate design is positive angular increments accumulated into theta. The exact differentiable parameterization is a project hypothesis and must be validated experimentally.

## 5. Repository Boundary

```text
pipeline/workflows/turntable/
├── workflow.py
├── legacy_v13/              # frozen baseline
├── pose/
│   ├── single_axis.py
│   ├── hypotheses.py        # later
│   ├── global_orbit.py      # later
│   └── observability.py     # later
├── benchmark/
│   ├── profiles.py
│   └── metrics.py
└── gaussian/                # introduced at RotGS reproduction
```

Synthetic data remains inside:

`workspace/research/turntable/synthetic/<dataset_name>/`

Real user capture remains inside:

`workspace/runs/<run_id>/`

## 6. Experimental Protocol

Every pose change must first pass synthetic evaluation in this order:

1. `uniform_360`
2. `nonuniform_360`
3. `nonuniform_280`
4. real Turntable regression run

Do not promote a pose method merely because it creates more sparse points.

Evaluate: axis error, angle MAE, increment MAE, span error, cycle consistency, trajectory continuity, and real sparse quality.

## 7. R0.1 Command

```powershell
blender.exe --background `
  --python tools/turntable_synthetic_blender.py -- `
  --model ".\workspace\runs\<orbit_run>\output\<model>.glb" `
  --output ".\workspace\research\turntable\synthetic\chair_nonuniform_280" `
  --profile nonuniform_280 `
  --frames 60
```

Prediction schema:

```json
{
  "axis": [0.0, 0.0, 1.0],
  "angles_deg": [0.0, 1.2, 2.8, 4.1]
}
```

Score:

```powershell
python tools/turntable_benchmark_report.py `
  --ground-truth ".\workspace\research\turntable\synthetic\chair_nonuniform_280\ground_truth.json" `
  --prediction ".\prediction.json"
```

## 8. R0.1 Success Criteria

- pure-Python tests pass;
- Blender renders at least one profile from a real GLB;
- frame/mask/GT counts match;
- GT trajectory is exact and deterministic;
- a gauge-equivalent perfect prediction scores approximately zero;
- then move to image-based structured estimation, not directly to GLB/PLY.
