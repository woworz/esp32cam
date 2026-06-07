# 前端 - 原理文档

> 本文档解释前端 SPA 的**架构设计**、**工作原理**和**关键机制**。

---

## 页面结构与状态管理

### 单页应用（SPA）

前端为**纯静态单页应用**，无框架（无 React/Vue），完全基于原生 DOM API：

```
index.html          页面骨架 + 语义化元素
    │
    ├──► css/style.css   样式与布局
    └──► js/app.js       逻辑与交互
```

**为什么不用框架？** 项目需求简单（展示图片列表 + 统计 + 远程控制），原生 JS 足够，避免引入框架带来的构建步骤和运行时开销。

### 状态管理

前端状态存储在**模块级变量**中，非全局状态树：

```javascript
let refreshTimer = null;   // 自动刷新定时器 ID
let isLoading = false;     // 加载中标志（防止重复请求）
```

**为什么没有 Redux/Vuex？** 状态数量少（仅加载状态和定时器 ID），使用全局变量足够，避免过度工程化。

### DOM 结构

| 区域 | 对应 ID | 职责 |
|------|---------|------|
| 页头 | `.header` | 标题 + 照片总数 |
| 控制区 | `.control-cards` | ESP32 实时预览 + 统计面板 |
| 统计面板 | `.stats-grid` | 已处理数 / 原始数 / 总大小 |
| 操作区 | `.actions` | 刷新按钮 + 远程拍照按钮 |
| 图片区 | `.image-grid` | 照片画廊（动态生成） |
| 通知 | `#toast` | 操作反馈（滑入动画） |

---

## 前端架构与数据流

### 架构模式

采用**命令式 DOM 操作** + **函数式工具函数**的混合模式：

```
用户操作 / 定时器
    │
    ▼
事件处理函数 (deleteImage, triggerCapture)
    │
    ▼
apiRequest()  ──► fetch() ──► 后端 API
    │
    ▼
响应处理 ──► 更新 DOM / showToast()
    │
    ▼
loadImages() / loadStats()  ──► 重新渲染对应区域
```

### API 请求封装

`apiRequest()` 是对 `fetch()` 的薄封装：

```javascript
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, { ...options });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return await response.json();
    }
    return response;
}
```

**设计意图**：
- 统一 API 基础地址，避免每个请求都写完整 URL
- 自动 JSON 解析，减少样板代码
- 错误统一抛出，由调用方 `try/catch` + `showToast` 处理

---

## 自动轮询机制

### 定时器管理

前端通过 `setInterval` 实现**自动刷新**：

```javascript
function startAutoRefresh() {
    refreshTimer = setInterval(() => {
        loadImages();
        loadStats();
    }, REFRESH_INTERVAL);  // 10000ms = 10秒
}
```

### 页面可见性优化

利用 **Page Visibility API** 节省资源：

```javascript
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();   // 切出标签页时暂停
    } else {
        startAutoRefresh();  // 切回时恢复
        loadImages();
        loadStats();
    }
});
```

**为什么需要这个优化？** 若用户将页面切到后台，轮询仍会持续消耗网络和 CPU。通过监听 `visibilitychange`，在后台时暂停轮询，切回时立即刷新，兼顾实时性和资源效率。

### 首次加载与刷新策略

| 场景 | 行为 |
|------|------|
| 页面首次加载 | 立即执行 `loadStats()` + `loadImages()` + `startAutoRefresh()` |
| 用户点击"刷新" | 手动调用 `loadStats()` / `loadImages()` |
| 删除图片后 | 成功后立即 `loadImages()` 更新列表 |
| 远程拍照后 | 2 秒延迟后 `loadImages()` + `loadStats()`（等待 ESP32 上传完成） |
| 标签页后台 | 暂停轮询 |
| 标签页前台 | 恢复轮询 + 立即刷新 |

---

## 图片画廊渲染

### 虚拟滚动？不，直接 DOM

`renderImageGrid(images)` 直接操作 DOM：

```javascript
function renderImageGrid(images) {
    const grid = document.getElementById('image-grid');
    grid.innerHTML = '';  // 清空现有内容
    
    images.forEach(img => {
        const card = document.createElement('div');
        card.className = 'image-card';
        card.innerHTML = `
            <img src="${API_BASE_URL}/image/${img.filename}" ...>
            <div class="image-info">
                <span>${formatDate(img.created)}</span>
                <span>${formatSize(img.size)}</span>
            </div>
            <button onclick="deleteImage('${img.filename}')">删除</button>
        `;
        grid.appendChild(card);
    });
}
```

**为什么不用虚拟滚动？** 项目场景下图片数量通常不超过几百张，直接 `innerHTML` 或 `appendChild` 性能足够。虚拟滚动在千条以上数据时才显现优势。

### 图片懒加载

`<img>` 标签直接使用 `src`，无懒加载。考虑到：
- 图片尺寸已压缩（处理后约 20-50KB）
- 网格默认显示 20-30 张，带宽压力小
- 添加懒加载需引入 `IntersectionObserver`，增加复杂度

若未来图片数量增长，可轻松添加 `loading="lazy"` 原生懒加载。

---

## 样式系统

### CSS 变量主题

使用 **CSS 自定义属性**（变量）定义暗色主题：

```css
:root {
    --primary-color: #e74c3c;      /* 主色：红色 */
    --bg-color: #1a1a2e;           /* 背景：深蓝黑 */
    --card-bg: #16213e;             /* 卡片：深蓝 */
    --text-color: #eaeaea;          /* 文字：浅灰 */
    --border-color: #0f3460;        /* 边框：深蓝 */
}
```

**优势**：集中管理颜色，未来支持亮色主题时只需修改变量值。

### 响应式布局

| 断点 | 布局变化 |
|------|----------|
| `> 768px` | 控制区 3 列、统计 2x2、图片网格自适应多列 |
| `<= 768px` | 控制区单列、统计单列、图片网格 2 列、缩小字号 |

**实现方式**：CSS Grid + Flexbox + `@media` 媒体查询，无第三方框架。

### 动画设计

| 动画 | 触发 | 效果 |
|------|------|------|
| `pulse` | 页面加载 | LIVE 标签呼吸效果（缩放 1.0 → 1.1 → 1.0） |
| `slideIn` | Toast 显示 | 从右侧滑入 |
| `fadeIn` | 图片卡片首次渲染 | 透明度 0 → 1 |
| 卡片悬浮 | 鼠标 hover | 上移 5px + 阴影加深 |
| 删除按钮 | 卡片 hover | 从透明渐显 |

**性能**：所有动画仅使用 `transform` 和 `opacity`，触发 GPU 加速，不引起重排。

---

## 交互设计

### 删除确认

`deleteImage()` 使用原生 `confirm()` 对话框：

```javascript
if (!confirm(`确定要删除 ${filename} 吗？`)) {
    return;
}
```

**为什么不用自定义模态框？** 减少 DOM 和 JS 复杂度，原生 `confirm` 足够且用户体验一致。

### 操作反馈

所有用户操作均通过 `showToast()` 提供反馈：

```javascript
showToast('删除成功', 'success');   // 绿色 Toast，2 秒后消失
showToast('删除失败', 'error');      // 红色 Toast
showToast('正在加载...', 'info');    // 蓝色 Toast
```

实现原理：为 `#toast` 元素添加 `.show` 类（触发 CSS 动画），`setTimeout` 2 秒后移除。

### 防重复提交

`isLoading` 标志防止用户快速点击导致重复请求：

```javascript
async function triggerCapture() {
    if (isLoading) return;   // 若正在处理，忽略本次点击
    isLoading = true;
    
    try {
        await apiRequest('/trigger', { method: 'POST' });
        showToast('拍照指令已发送', 'success');
    } finally {
        isLoading = false;   // 无论成功失败，恢复可点击状态
    }
}
```

---

## 实时预览

### ESP32 视频流嵌入

实时预览通过 `<img>` 标签直接引用 ESP32 的 MJPEG 流：

```html
<img id="esp32-stream" src="http://<esp32-ip>/stream" alt="实时视频流">
```

浏览器会自动识别 `multipart/x-mixed-replace` 响应，逐帧替换显示。

### 流状态检测

`loadStats()` 同时更新 ESP32 连接状态：

```javascript
// 若 ESP32 不可达，显示离线状态
if (stats.esp32_url) {
    statusEl.textContent = '在线';
    statusEl.className = 'status-online';
} else {
    statusEl.textContent = '未配置';
    statusEl.className = 'status-offline';
}
```

**注意**：前端不直接 ping ESP32，而是依赖后端 `/api/stats` 返回的 `esp32_configured` 字段判断。
