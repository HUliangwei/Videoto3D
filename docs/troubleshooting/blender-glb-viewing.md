# Blender 中查看 GLB 的正确方式

## 现象

通过 Blender 的 glTF Import 导入 `.glb` 后，模型可能显示为灰白色，看起来像“没有纹理”。

## 原因

Blender 的 **Solid** 视图默认不会显示材质纹理。GLB 本身可能已经完整嵌入材质和纹理。

## 正确查看

推荐使用 Videoto3D：

```powershell
python app.py view glb --run teddy_001
```

或直接查看任意 GLB：

```powershell
python app.py view glb --path "D:\Models\teddy.glb"
```

Videoto3D Viewer 会自动切换到 **Material Preview**。

手工 Blender 操作：导入 glTF 2.0 后，按 `Z` → `Material Preview`。

## 不要这样打开

```text
blender.exe file.glb
```

Blender 命令行会尝试把位置参数当作 Blender 工程文件打开；`.glb` 应通过 glTF Import 导入，而不是作为 `.blend` 工程直接打开。
