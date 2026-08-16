# @videoto3d/viewer

Reusable browser 3D asset viewer. It intentionally has **no knowledge of Videoto3D runs, APIs, COLMAP, OpenMVS, Brush training, or workspace paths**.

Public API:

```tsx
<AssetViewer type="glb" src="/model.glb" />
<AssetViewer type="splat" src="/model.ply" />
```

GLB uses Three.js `GLTFLoader`; Gaussian Splat uses Spark. The module is designed so it can later be moved into a portfolio/personal-site project without carrying the Videoto3D control layer.
