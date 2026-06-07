# 服务端 - 实现文档

> 本文档记录 Flask 后端 API 服务中每个函数/类的**定义位置**（文件 + 行号），用于快速定位代码。

---

## app.py

文件：`server/app.py`（66 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `create_app` | 35 | `create_app() -> Flask` | **应用工厂函数**。创建 Flask 实例、注册 Blueprint、配置 CORS、创建上传目录 |
| `app` | 61 | 模块级变量 | `create_app()` 的返回实例，供外部导入使用 |
| `__main__` | 64 | `if __name__ == "__main__":` | 主入口，以 `HOST:PORT` 启动开发服务器 |

---

## config.py

文件：`server/config.py`（55 行）

> 本文件无函数定义，全部为配置常量。

| 常量 | 行号 | 默认值 | 说明 |
|------|------|--------|------|
| `HOST` | 21 | `"0.0.0.0"` | 监听地址 |
| `PORT` | 22 | `5000` | 监听端口 |
| `UPLOAD_FOLDER` | 25 | `"uploads"` | 原始图片存储目录 |
| `PROCESSED_FOLDER` | 26 | `"processed"` | 处理后图片存储目录 |
| `FORWARD_URL` | 31 | `None` | 图片转发目标 URL（可选） |
| `ESP32_URL` | 36 | `None` | ESP32 拍照触发地址（用于 `/trigger`） |
| `FONT_PATH` | 42 | `None` | 自定义字体路径（解决中文乱码） |
| `TEXT_POSITION` | 45 | `"bottom"` | 时间戳文字叠加位置（top/bottom/center） |
| `TEXT_COLOR` | 48 | `(255, 255, 255)` | 文字颜色（白色 RGB） |
| `TEXT_BG_COLOR` | 51 | `(0, 0, 0, 128)` | 文字背景色（半透明黑 RGBA） |
| `CORS_ORIGINS` | 55 | `["*"]` | 允许的 CORS 跨域来源 |

---

## routes/api.py

文件：`server/routes/api.py`（208 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `api_bp` | 30 | `api_bp = Blueprint('api', __name__)` | Blueprint 实例，所有 API 端点注册于此 |
| `upload` | 34 | `upload()` | **POST /upload**。接收 ESP32 上传的多媒体图片，调用 `save_and_process_image()` 处理 |
| `get_image` | 69 | `get_image(filename)` | **GET /image/<filename>**。查找并返回指定图片文件（优先 `processed/`，其次 `uploads/`） |
| `latest` | 89 | `latest()` | **GET /latest**。返回最新处理后的图片文件 |
| `api_images` | 104 | `api_images()` | **GET /api/images**。返回 JSON 格式图片列表（含文件名、大小、时间、URL） |
| `api_delete_image` | 127 | `api_delete_image(filename)` | **DELETE /api/image/<filename>**。删除指定图片（原始 + 处理后） |
| `api_stats` | 144 | `api_stats()` | **GET /api/stats**。返回系统统计信息（图片数量、大小、ESP32 配置状态） |
| `trigger_capture` | 168 | `trigger_capture()` | **GET/POST /trigger**。向 `ESP32_URL` 发送 HTTP 请求，远程触发拍照 |

**API 端点汇总表：**

| 方法 | 路径 | 处理函数 | 行号 | 功能 |
|------|------|----------|------|------|
| POST | `/upload` | `upload()` | 34 | 接收 ESP32 上传的图片 |
| GET | `/image/<fn>` | `get_image()` | 69 | 获取指定图片文件 |
| GET | `/latest` | `latest()` | 89 | 获取最新处理图片 |
| GET | `/api/images` | `api_images()` | 104 | JSON 格式图片列表 |
| DELETE | `/api/image/<fn>` | `api_delete_image()` | 127 | 删除图片 |
| GET | `/api/stats` | `api_stats()` | 144 | JSON 格式统计信息 |
| GET/POST | `/trigger` | `trigger_capture()` | 168 | 远程触发 ESP32 拍照 |

---

## services/image_service.py

文件：`server/services/image_service.py`（214 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `save_and_process_image` | 33 | `save_and_process_image(file_storage, custom_text="", position=None)` | **保存并处理图片**。保存原始文件 → 叠加时间戳 → 保存处理后文件 |
| `find_image_path` | 87 | `find_image_path(filename) -> Optional[str]` | **查找图片路径**。优先 `processed/`，找不到再查 `uploads/` |
| `get_latest_processed_image` | 108 | `get_latest_processed_image() -> Optional[str]` | 获取最新处理后图片的完整路径 |
| `list_images` | 128 | `list_images() -> List[Dict]` | 获取所有处理后图片列表，按时间倒序排列 |
| `delete_image` | 151 | `delete_image(filename) -> bool` | 删除指定图片（先删 `processed/`，再删 `uploads/`） |
| `get_stats` | 182 | `get_stats(esp32_url) -> Dict` | 获取系统统计信息（图片数量、总大小、ESP32 配置状态） |

---

## utils/image_processor.py

文件：`server/utils/image_processor.py`（137 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `add_text_overlay` | 21 | `add_text_overlay(image_path, text, output_path, position="bottom", text_color=(255,255,255), bg_color=(0,0,0,128), font_path=None)` | **在图片上叠加文字**。创建 RGBA 叠加层 → 绘制半透明背景 → 绘制文字 → 合并保存 |
| `build_timestamp_text` | 122 | `build_timestamp_text(custom_text="")` | **构建时间戳字符串**。格式：`"自定义文字  |  YYYY-MM-DD HH:MM:SS"` |

---

## 模块间调用关系速查

```
app.py::create_app()                          [app.py:35]
    │
    ├─→ routes/api.py::api_bp                  [routes/api.py:30]
    │       │
    │       ├─→ upload()                       [routes/api.py:34]
    │       │       └─→ save_and_process_image() [services/image_service.py:33]
    │       │               ├─→ add_text_overlay() [utils/image_processor.py:21]
    │       │               └─→ build_timestamp_text() [utils/image_processor.py:122]
    │       │
    │       ├─→ get_image()                    [routes/api.py:69]
    │       │       └─→ find_image_path()        [services/image_service.py:87]
    │       │
    │       ├─→ latest()                         [routes/api.py:89]
    │       │       └─→ get_latest_processed_image() [services/image_service.py:108]
    │       │
    │       ├─→ api_images()                     [routes/api.py:104]
    │       │       └─→ list_images()              [services/image_service.py:128]
    │       │
    │       ├─→ api_delete_image()               [routes/api.py:127]
    │       │       └─→ delete_image()              [services/image_service.py:151]
    │       │
    │       ├─→ api_stats()                      [routes/api.py:144]
    │       │       └─→ get_stats()                 [services/image_service.py:182]
    │       │
    │       └─→ trigger_capture()                 [routes/api.py:168]
    │               └─→ requests.get/post(ESP32_URL) [外部 HTTP]
    │
    ├─→ config.py (导入所有配置常量)              [config.py:21-55]
    │
    └─→ flask_cors.CORS(app, origins=CORS_ORIGINS)
```
