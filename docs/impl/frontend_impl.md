# 前端 - 实现文档

> 本文档记录前端 SPA 中每个函数/关键元素的**定义位置**（文件 + 行号），用于快速定位代码。

---

## index.html

文件：`frontend/index.html`（113 行）

| 元素 ID | 行号 | 说明 |
|---------|------|------|
| `photo-count` | 17 | 照片总数显示（标题栏） |
| `esp32-status` | 21 | ESP32 连接状态文本 |
| `esp32-card` | 30 | ESP32 实时预览卡片容器 |
| `esp32-stream` | 36 | ESP32 实时视频流图片（`src` 指向 `/stream`） |
| `esp32-fullscreen` | 42 | 全屏查看链接 |
| `triggerCapture()` | 43 | 远程拍照按钮（`onclick`） |
| `processed-count` | 55 | 已处理图片数（统计面板） |
| `raw-count` | 59 | 原始图片数（统计面板） |
| `total-size` | 63 | 总大小（统计面板） |
| `loadStats()` | 86 | 刷新统计按钮（`onclick`） |
| `loadImages()` | 87 | 刷新图片按钮（`onclick`） |
| `image-grid` | 97 | 图片网格容器 |
| `toast` | 109 | Toast 通知元素 |

---

## css/style.css

文件：`frontend/css/style.css`（430 行）

> 本文件无函数定义，记录关键 CSS 选择器的位置。

| 选择器 | 行号 | 说明 |
|--------|------|------|
| `:root` | 1 | CSS 变量定义（主色调、背景色、卡片色等） |
| `*` / `body` | 11 | 全局重置与 body 样式（暗色背景、无滚动条） |
| `.header` | 16 | 页头：深色渐变背景、固定高度、Flex 布局 |
| `.control-cards` | 80 | 控制卡片容器：CSS Grid 三列布局 |
| `.stream-container` | 111 | 视频流容器：固定 4:3 比例、圆角、溢出隐藏 |
| `.live-badge` | 131 | LIVE 标签：绝对定位、红色背景、脉冲动画（`@keyframes pulse`） |
| `.stats-grid` | 158 | 统计格子：2x2 Grid 布局、渐变背景卡片 |
| `.btn-primary` | 212 | 主按钮：红色渐变背景、悬浮提升效果 |
| `.btn-secondary` | 229 | 次按钮：半透明背景、边框 |
| `.image-grid` | 259 | 图片网格：自适应列数（`repeat(auto-fill, minmax(220px, 1fr))`） |
| `.image-card` | 265 | 图片卡片：圆角、阴影、悬浮放大动画 |
| `.btn-delete` | 304 | 删除按钮：红色背景、默认隐藏、卡片悬浮时显示 |
| `.toast` | 359 | Toast 通知：固定右下角、透明背景、模糊效果 |
| `.toast.show` | 375 | Toast 显示状态：滑入动画 + 淡入 |
| `@keyframes slideIn` | 380 | 从右侧滑入动画 |
| `@keyframes fadeIn` | 386 | 淡入动画 |
| `@keyframes pulse` | 392 | LIVE 标签脉冲缩放动画 |
| `@media (max-width: 768px)` | 403 | **移动端响应式断点**：单列布局、缩小字号 |

---

## js/app.js

文件：`frontend/js/app.js`（308 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `API_BASE_URL` | 7 | 常量 | 后端 API 基础地址（默认 `http://localhost:5000`） |
| `REFRESH_INTERVAL` | 8 | 常量 = `10000` | 自动刷新间隔（10 秒） |
| `refreshTimer` | 11 | 变量 | `setInterval` 返回的定时器 ID |
| `isLoading` | 12 | 变量 | 加载状态标志（防止重复请求） |
| `showToast` | 18 | `showToast(message, type = 'info')` | 显示 Toast 通知。`type` 可选 `info`/`success`/`error` |
| `formatSize` | 38 | `formatSize(bytes)` | 格式化文件大小（B/KB/MB/GB） |
| `formatDate` | 45 | `formatDate(dateString)` | 格式化日期为本地字符串 |
| `apiRequest` | 57 | `apiRequest(endpoint, options = {})` | **API 请求封装**。基于 `fetch`，自动拼接 `API_BASE_URL`，处理 JSON 解析和错误 |
| `loadStats` | 84 | `loadStats()` | **加载系统统计**。调用 `GET /api/stats`，更新统计面板和 ESP32 状态 |
| `loadImages` | 124 | `loadImages()` | **加载图片列表**。调用 `GET /api/images`，渲染图片网格 |
| `renderImageGrid` | 155 | `renderImageGrid(images)` | **渲染图片网格**。根据图片数组生成 DOM 卡片，绑定删除按钮事件 |
| `deleteImage` | 186 | `deleteImage(filename)` | **删除图片**。先 `confirm` 确认，调用 `DELETE /api/image/<fn>`，成功后动画移除 DOM 并更新计数 |
| `triggerCapture` | 233 | `triggerCapture()` | **远程触发拍照**。调用 `GET/POST /trigger`，成功后 2 秒延迟刷新图片和统计 |
| `startAutoRefresh` | 259 | `startAutoRefresh()` | **启动自动刷新**。每 10 秒执行 `loadImages()` + `loadStats()` |
| `stopAutoRefresh` | 270 | `stopAutoRefresh()` | **停止自动刷新**。清除 `refreshTimer` |
| `DOMContentLoaded` | 281 | 事件监听 | **初始化入口**。页面加载完成后：加载统计 → 加载图片 → 启动自动刷新 |
| `visibilitychange` | 295 | 事件监听 | **页面可见性监听**。页面 hidden 时暂停刷新，visible 时恢复 |
| `window.deleteImage` | 305 | 全局暴露 | 将 `deleteImage` 绑定到 `window`，供 HTML `onclick` 调用 |
| `window.triggerCapture` | 306 | 全局暴露 | 将 `triggerCapture` 绑定到 `window` |
| `window.loadStats` | 307 | 全局暴露 | 将 `loadStats` 绑定到 `window` |

---

## 前端调用关系速查

```
页面加载
    │
    ▼
DOMContentLoaded [js/app.js:281]
    │
    ├─→ loadStats()          [js/app.js:84]
    │       └─→ apiRequest('/api/stats')    [js/app.js:57]
    │               └─→ GET http://localhost:5000/api/stats
    │
    ├─→ loadImages()         [js/app.js:124]
    │       └─→ apiRequest('/api/images')   [js/app.js:57]
    │               └─→ GET http://localhost:5000/api/images
    │                       └─→ renderImageGrid(images) [js/app.js:155]
    │                               ├─→ formatSize()     [js/app.js:38]
    │                               ├─→ formatDate()     [js/app.js:45]
    │                               └─→ 绑定 deleteImage() 到每张卡片的删除按钮
    │
    └─→ startAutoRefresh()   [js/app.js:259]
            └─→ setInterval(() => { loadImages(); loadStats(); }, 10000)

用户操作
    │
    ├─→ 点击"删除" → deleteImage(filename)    [js/app.js:186]
    │       └─→ apiRequest(DELETE /api/image/<fn>)
    │               └─→ 成功后: 动画移除 DOM → showToast() → loadImages()
    │
    ├─→ 点击"拍照" → triggerCapture()         [js/app.js:233]
    │       └─→ apiRequest(/trigger)
    │               └─→ 成功后: setTimeout(2000) → loadImages() + loadStats()
    │
    └─→ 点击"刷新" → loadImages() / loadStats()

页面可见性变化
    │
    ├─→ hidden  → stopAutoRefresh()   [js/app.js:270]
    └─→ visible → startAutoRefresh()  [js/app.js:259]
```
