# 前端实现

前端由服务器 Nginx 直接托管，API 使用空的 `API_BASE_URL`，因此所有请求与网页同源。

## 页面组件

- 顶栏：照片总数和设备在线状态。
- 云端设备控制：最后心跳、远程拍照按钮。
- 系统统计：处理图、原图、存储大小、待执行命令。
- API 信息：当前公网接口。
- 图片画廊：查看和删除处理图。
- 图片下载：每张图片左上角的下载按钮调用 `/download/<filename>`。

旧的 ESP32 MJPEG `<img>`、全屏流链接和局域网地址推导逻辑已删除。

## JavaScript 数据流

```text
DOMContentLoaded
  ├─ GET /api/stats
  │   ├─ device_online → 在线/离线
  │   ├─ device_last_seen → 最后心跳
  │   └─ pending_commands → 待执行命令
  ├─ GET /api/images → 渲染画廊
  └─ 每 10 秒刷新

点击远程拍照
  └─ POST /trigger
      └─ 每 2 秒 GET /api/commands/<id>
          ├─ completed → 刷新图片并提示完成
          └─ failed → 显示设备错误
```

## 关键函数

| 函数 | 说明 |
|---|---|
| `apiRequest()` | 同源 Fetch 封装 |
| `loadStats()` | 更新图片、设备和命令统计 |
| `loadImages()` | 获取图片列表 |
| `renderImageGrid()` | 渲染图片卡片 |
| `deleteImage()` | 删除服务器图片 |
| `triggerCapture()` | 创建云端拍照命令 |
| `waitForCommand()` | 等待 ESP32 回报命令结果 |
