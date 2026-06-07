# 服务端 - 原理文档

> 本文档解释 Flask 后端 API 服务各模块的**工作原理**、**设计思路**和**关键机制**。

---

## 应用工厂模式

### 为什么使用应用工厂？

`server/app.py` 采用 **Flask Application Factory** 模式（`create_app()` 函数），而非全局 `app = Flask(__name__)`：

```python
def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix='')
    CORS(app, origins=CORS_ORIGINS)
    # ...
    return app

app = create_app()
```

**优势**：
1. **可测试性**：单元测试可独立创建应用实例，避免全局状态污染
2. **可配置性**：未来可通过参数 `create_app(config_name='production')` 加载不同配置
3. **延迟初始化**：蓝图、CORS、目录创建均在函数内部完成，导入模块时不产生副作用

### 目录自动创建

`create_app()` 运行时自动创建 `uploads/` 和 `processed/` 目录：

```python
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
```

使用 `exist_ok=True` 避免目录已存在时抛出异常，确保服务重启无故障。

---

## API 路由设计

### Blueprint 组织

所有 API 端点集中在 `routes/api.py` 的 `api_bp` Blueprint 中：

```python
api_bp = Blueprint('api', __name__)

@api_bp.route('/upload', methods=['POST'])
def upload(): ...

@api_bp.route('/api/images', methods=['GET'])
def api_images(): ...
```

**设计意图**：
- 将路由逻辑与应用工厂分离，便于单元测试（可直接测试 Blueprint）
- 未来如需版本控制，可轻松添加 `url_prefix='/v1'`

### RESTful 设计

| 设计原则 | 体现 |
|----------|------|
| 资源导向 | `/api/images`、`/api/stats` 表示资源集合 |
| HTTP 动词 | POST（创建）、GET（读取）、DELETE（删除） |
| 状态码 | 200 OK、400 Bad Request、404 Not Found、500 Internal Server Error |
| JSON 统一响应 | 所有响应包含 `{"status": "ok|error", ...}` |

### CORS 配置

前端 SPA 运行在 `localhost:8080`，后端在 `localhost:5000`，属于**跨域请求**：

```python
CORS(app, origins=CORS_ORIGINS)  # CORS_ORIGINS = ["*"]
```

`flask-cors` 自动为所有响应添加 `Access-Control-Allow-Origin: *` 头，允许浏览器跨域访问。

---

## 业务逻辑层

### 分层架构

```
routes/api.py       ← HTTP 请求/响应处理（Controller）
        │
        ▼
services/image_service.py  ← 业务逻辑（Service）
        │
        ▼
utils/image_processor.py   ← 底层工具（Util）
```

**分层原则**：
- **Controller**（`api.py`）：仅负责解析请求参数、调用 Service、返回响应，不处理业务逻辑
- **Service**（`image_service.py`）：封装核心业务（保存、查询、删除、统计），可被多个 Controller 复用
- **Util**（`image_processor.py`）：纯函数工具，无状态，可被任意层调用

### 图片保存与处理流程

`save_and_process_image()` 的完整工作流：

```
file_storage (Flask FileStorage)
    │
    ▼
生成 UUID 文件名 ──→ 保存原始文件到 uploads/{uuid}.jpg
    │
    ▼
build_timestamp_text(custom_text)
    └── "ESP32-S3 CAM  |  2024-01-01 12:00:00"
    │
    ▼
add_text_overlay(
    uploads/{uuid}.jpg,
    "ESP32-S3 CAM  |  2024-01-01 12:00:00",
    processed/{uuid}.jpg
)
    │
    ├──► 打开原图 → 转为 RGBA 模式
    ├──► 创建透明叠加层 (Image.new('RGBA', ...))
    ├──► 根据 position 计算文字坐标
    ├──► 绘制半透明背景矩形 (ImageDraw.rectangle)
    ├──► 绘制文字 (ImageDraw.text)
    ├──► alpha_composite 合并叠加层到原图
    └──► 转回 RGB 模式 → 保存 JPEG (quality=90)
    │
    ▼
[可选] 转发到 FORWARD_URL
    │
    ▼
返回 {"raw": "uuid.jpg", "processed": "uuid.jpg", "text": "..."}
```

### 双目录策略

- **`uploads/`**：保存 ESP32 上传的原始 JPEG，保留原始数据
- **`processed/`**：保存叠加时间戳后的图片，供前端展示

**为什么保留原始文件？** 便于调试、重处理（如更换字体、调整位置）和归档。

### 图片查找与删除的优先级

`find_image_path()` 和 `delete_image()` 均优先操作 `processed/`：

```python
def find_image_path(filename):
    processed = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(processed):
        return processed
    raw = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(raw):
        return raw
    return None
```

**设计意图**：前端展示的是处理后的图片，因此查找和删除操作优先面向 `processed/`。若用户直接访问 `/image/<fn>` 且 `processed/` 中不存在，则回退到 `uploads/`。

---

## 图片处理原理

### RGBA 叠加层技术

`add_text_overlay()` 使用 **RGBA 叠加层**实现半透明背景和文字：

```
原图 (RGB) ──► 转换为 RGBA ──►
                                    ├──► alpha_composite ──► 转回 RGB ──► 保存 JPEG
叠加层 (RGBA) ──► 绘制半透明矩形 + 文字 ──►
```

**为什么不用直接绘制？** Pillow 的 `ImageDraw` 直接在 RGB 图像上绘制时，文字背景无法设置透明度。通过创建独立的 RGBA 叠加层，可以自由控制背景色的 Alpha 通道（透明度）。

### 字体加载策略

字体加载采用**多级回退**策略：

```python
font = None
if font_path and os.path.exists(font_path):
    font = ImageFont.truetype(font_path, 40)
elif os.path.exists("C:/Windows/Fonts/simhei.ttf"):
    font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 40)
elif os.path.exists("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
    font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 40)
else:
    font = ImageFont.load_default()
```

| 优先级 | 字体 | 平台 |
|--------|------|------|
| 1 | 用户自定义 `FONT_PATH` | 任意 |
| 2 | SimHei (黑体) | Windows |
| 3 | WenQuanYi Zen Hei | Linux |
| 4 | Pillow 默认位图字体 | 任意（无中文支持） |

**为什么需要中文字体？** 默认字体不支持中文，若不配置中文字体，叠加的时间戳文字将显示为方块（□）。

### 文字位置计算

根据 `TEXT_POSITION`（top/bottom/center）计算文字坐标：

```python
if position == "bottom":
    y = height - text_height - 20   # 底部留 20px 边距
elif position == "top":
    y = 20                           # 顶部留 20px 边距
else:  # center
    y = (height - text_height) // 2  # 垂直居中
```

文字始终**水平居中**（`x = (width - text_width) // 2`）。

---

## 配置管理

### 配置分离原则

所有配置项集中在 `config.py`，应用通过导入使用：

```python
from config import HOST, PORT, UPLOAD_FOLDER, ...
```

**优势**：
- 配置与代码分离，修改配置无需触碰业务逻辑
- 支持不同部署环境（开发/测试/生产）通过环境变量或外部文件覆盖

### 关键配置项说明

| 配置项 | 默认值 | 典型修改场景 |
|--------|--------|--------------|
| `HOST` | `0.0.0.0` | 仅本机测试时改为 `127.0.0.1` |
| `PORT` | `5000` | 端口冲突时修改 |
| `FORWARD_URL` | `None` | 需要图片转发到另一台服务器时设置 |
| `ESP32_URL` | `None` | **必须设置**，否则 `/trigger` 无法工作 |
| `FONT_PATH` | `None` | Windows 用户建议设为 `C:/Windows/Fonts/simhei.ttf` |
| `TEXT_POSITION` | `"bottom"` | 根据图片内容调整（风景照放 bottom，人像放 top） |
| `CORS_ORIGINS` | `["*"]` | 生产环境应限制为前端实际域名 |

---

## 远程触发机制

### `/trigger` 端点

`trigger_capture()` 向 ESP32 发送 HTTP 请求，实现**服务器 → ESP32 的反向控制**：

```python
resp = requests.get(ESP32_URL, timeout=5)   # ESP32_URL = "http://192.168.1.xxx/capture"
```

**时序**：
1. 前端点击"拍照" → 请求 `POST /trigger`
2. 服务端请求 `GET http://<esp32-ip>/capture`
3. ESP32 的 `_handle_client()` 收到 `/capture` → 设置 `capture_flag = True`
4. `_capture_worker()` 检测到标志 → 拍照 → 上传
5. 上传完成后，前端自动刷新图片列表

**为什么用 HTTP 轮询而非 WebSocket？** ESP32 的 MicroPython 资源有限，WebSocket 库占用内存较大，HTTP 长轮询更轻量。
