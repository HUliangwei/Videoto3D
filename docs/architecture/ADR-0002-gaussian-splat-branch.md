# ADR-0002: Gaussian Splat as a Parallel Output Branch

- Status: Accepted
- Version: V0.9
- Date: 2026-08-16

## Context

V0.8 established a stable Run model and a successful photogrammetry branch: RGB + SAM2 + COLMAP → OpenMVS → OBJ → GLB. Gaussian Splatting should reuse the expensive/common acquisition and camera-estimation stages without coupling the public CLI to one third-party implementation.

## Decision

Expose the public operations as:

```text
python app.py run splat --run <run_id>
python app.py view splat --run <run_id>
```

Brush is an adapter behind those commands, not part of the public command name.

Each Run owns a Brush staging area:

```text
brush/dataset/images
brush/dataset/masks
brush/dataset/sparse/0
brush/exports
brush/recipe.json
```

The staging dataset is rebuilt from Run-local RGB, SAM2 masks, and the existing COLMAP sparse model. Source files are hard-linked when possible and copied otherwise. Brush exports remain as checkpoints; the latest completed export is exposed as the canonical `output/<run_id>_splat.ply`.

## Consequences

- Mesh/GLB and Gaussian Splat are independent sibling outputs.
- No additional SfM pass is required for Brush.
- Future Gaussian Splat engines can replace Brush without renaming the CLI.
- The Web GUI can present GLB and Splat as two output cards for one Run.
- Brush-specific parameters are stored in `brush/recipe.json` and the `splat` manifest stage.
