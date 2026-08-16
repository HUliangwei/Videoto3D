# README Demo Media

该目录用于 GitHub README 的轻量展示媒体。

推荐最终结构：

```text
docs/assets/demo/
├─ workflow-video-cover.png     # 16:9 教学视频封面
├─ workflow-demo.gif            # 10–30 秒 README 短预览，可选
├─ artifact-inspector.png       # 中间产物 GUI 截图
├─ mesh-result.png
└─ splat-result.png
```

`recordings/` 中的 OBS 原始视频不要提交到 Git。

## 完整教学视频推荐发布方式

### 方案 A：GitHub user attachment

在 GitHub Issue / PR / Discussion 的编辑框中上传 H.264 MP4，GitHub 会生成 `github.com/user-attachments/...` 地址。  
把生成的地址放到根目录 `README.md` 的 `WORKFLOW_VIDEO` 区域。

GitHub 当前支持 `.mp4` / `.mov` / `.webm`，并推荐 H.264 以获得更好的浏览器兼容性。

### 方案 B：Bilibili / YouTube / 个人网站

README 保留封面图：

```markdown
[![Videoto3D Workflow Tutorial](docs/assets/demo/workflow-video-cover.png)](<VIDEO_URL>)
```

点击封面进入完整视频。

### README 内只保留轻量预览

完整 1080p Master 不应直接进入普通 Git 历史。  
README 如果需要动态预览，建议制作 720p、10–15 FPS 的短 GIF / WebP，并控制文件大小。
