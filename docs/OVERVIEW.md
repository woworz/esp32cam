# ESP32-S3 CAM 图传系统 - 项目总览

## 1. 系统概述

本项目是基于 **ESP32-S3 + OV3660 + ST7789 TFT** 的无线图传系统，采用**前后端分离**的三层架构：

- **ESP32 端**（MicroPython）：摄像头采集 + HTTP 服务器 + MJPEG 流推送 + WiFi 管理
- **后端 API 服务**（Flask + Python）：接收图片、叠加时间戳、提供 REST API
- **前端 SPA**（原生 HTML/CSS/JS）：照片画廊、实时预览、远程控制

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      ESP32-S3 端                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ OV3660   │  │ WiFi     │  │ HTTP Server (80)      │  │
│  │ 摄像头   │──│ Manager  │──│ - MJPEG 视频流          │  │
│  └──────────┘  └──────────┘  │ - 拍照上传             │  │
│       │                      │ - WiFi 配置页面        │  │
│       ▼                      └──────────┬───────────┘  │
│  ┌──────────┐                           │              │
│  │ ST7789   │                           │ HTTP POST    │
│  │ TFT 屏幕 │◄──────────────────────────┘              │
│  │ 240x320  │                                          │
│  └──────────┘                                          │
└─────────────────────────────────────────┼───────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Flask JSON API 服务端 (:5000)         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Flask Server (:5000)                              │  │
│  │ - POST /upload        接收图片，叠加时间戳        │  │
│  │ - GET  /api/images    图片列表 (JSON)            │  │
│  │ - GET  /api/stats     系统统计 (JSON)            │  │
│  │ - GET  /image/<fn>    获取指定图片               │  │
│  │ - GET  /latest        获取最新处理后的图片       │  │
│  │ - DEL  /api/image/<fn> 删除图片                  │  │
│  │ - GET|POST /trigger   远程触发ESP32拍照          │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ HTTP API (CORS)
                           │
┌─────────────────────────────────────────────────────────┐
│                   前端 SPA (端口 8080)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 独立前端应用                                       │  │
│  │ - index.html  +  css/style.css  +  js/app.js     │  │
│  │ - 照片画廊 / 实时预览 / 远程控制                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
esp_cam/
├── docs/                          # 项目文档
│   ├── README.md                  # 完整软件文档（硬件/接口/使用指南）
│   ├── OVERVIEW.md                # 本文档：项目总览
│   ├── impl/                      # 实现文档目录
│   │   ├── esp32_impl.md          # ESP32 实现文档
│   │   ├── server_impl.md         # 服务端实现文档
│   │   └── frontend_impl.md       # 前端实现文档
│   └── principle/                 # 原理文档目录
│       ├── esp32_principle.md     # ESP32 原理文档
│       ├── server_principle.md      # 服务端原理文档
│       └── frontend_principle.md  # 前端原理文档
│
├── esp32/                         # ESP32-S3 MicroPython 端
│   ├── boot.py                    # 启动引导 (自动执行)
│   ├── main_app.py                # 主程序 (HTTP服务器 + 拍照上传)
│   ├── ovcam.py                   # OV3660 摄像头驱动封装
│   ├── tft_display.py             # ST7789 TFT 显示屏驱动封装
│   ├── wifimgr.py                 # WiFi 连接管理
│   ├── wificonfig_server.py       # AP模式配置服务器
│   └── wifi_config.json           # WiFi 配置文件 (运行时生成)
│
├── server/                        # PC/后端 API 服务端
│   ├── app.py                     # Flask 应用工厂
│   ├── config.py                  # 配置文件
│   ├── requirements.txt           # Python 依赖
│   ├── uploads/                   # 原始上传图片 (运行时生成)
│   ├── processed/                 # 处理后图片 (运行时生成)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── api.py                 # API 路由 Blueprint
│   ├── services/
│   │   ├── __init__.py
│   │   └── image_service.py       # 图片业务逻辑层
│   └── utils/
│       ├── __init__.py
│       └── image_processor.py     # 图片处理工具
│
└── frontend/                      # 前端 SPA 应用
    ├── index.html                 # 主页面
    ├── css/
    │   └── style.css              # 样式文件
    ├── js/
    │   └── app.js                 # 前端逻辑
    └── README.md                  # 前端说明文档
```

---

## 4. 模块职责索引

### 4.1 ESP32 端（固件）

| 文件 | 行数 | 职责 | 实现文档 | 原理文档 |
|------|------|------|----------|----------|
| `esp32/boot.py` | 49 | 设备启动入口，WiFi 初始连接，失败则进入 AP 配置模式 | [impl](impl/esp32_impl.md#bootpy) | [principle](principle/esp32_principle.md#启动流程) |
| `esp32/main_app.py` | 553 | HTTP 服务器、MJPEG 流推送、拍照线程、按键监听、TFT 显示、图片上传 | [impl](impl/esp32_impl.md#main_apppy) | [principle](principle/esp32_principle.md#主程序与线程模型) |
| `esp32/ovcam.py` | 204 | OV3660 摄像头封装：初始化、拍照、分辨率/质量设置 | [impl](impl/esp32_impl.md#camerapy) | [principle](principle/esp32_principle.md#摄像头驱动) |
| `esp32/tft_display.py` | 239 | ST7789 TFT 驱动：SPI 通信、显示窗口、图片/文本渲染、背光控制 | [impl](impl/esp32_impl.md#tft_displaypy) | [principle](principle/esp32_principle.md#显示屏驱动) |
| `esp32/wifimgr.py` | 186 | WiFi 连接管理：配置加载/保存、扫描、连接、AP 模式 | [impl](impl/esp32_impl.md#wifimgrpy) | [principle](principle/esp32_principle.md#wi-fi-管理) |
| `esp32/wificonfig_server.py` | 199 | AP 模式下的 HTTP 配置服务器：WiFi 扫描页面、配置保存 | [impl](impl/esp32_impl.md#wificonfig_serverpy) | [principle](principle/esp32_principle.md#ap-配置服务器) |

### 4.2 服务端（后端）

| 文件 | 行数 | 职责 | 实现文档 | 原理文档 |
|------|------|------|----------|----------|
| `server/app.py` | 66 | Flask 应用工厂：创建实例、注册蓝图、配置 CORS、创建目录 | [impl](impl/server_impl.md#apppy) | [principle](principle/server_principle.md#应用工厂模式) |
| `server/config.py` | 55 | 配置常量：监听地址/端口、目录路径、字体、颜色、CORS | [impl](impl/server_impl.md#configpy) | [principle](principle/server_principle.md#配置管理) |
| `server/routes/api.py` | 208 | REST API 蓝图：7 个端点（上传/图片/列表/统计/触发/删除/最新） | [impl](impl/server_impl.md#routesapipy) | [principle](principle/server_principle.md#api-路由设计) |
| `server/services/image_service.py` | 214 | 图片业务逻辑：保存处理、列表查询、删除、统计、转发 | [impl](impl/server_impl.md#servicesimage_servicepy) | [principle](principle/server_principle.md#业务逻辑层) |
| `server/utils/image_processor.py` | 137 | 图片处理工具：RGBA 叠加层、文字渲染、时间戳构建、字体加载 | [impl](impl/server_impl.md#utilsimage_processorpy) | [principle](principle/server_principle.md#图片处理原理) |

### 4.3 前端（浏览器）

| 文件 | 行数 | 职责 | 实现文档 | 原理文档 |
|------|------|------|----------|----------|
| `frontend/index.html` | 113 | 单页应用 HTML：统计面板、实时预览、图片网格、Toast 通知 | [impl](impl/frontend_impl.md#indexhtml) | [principle](principle/frontend_principle.md#页面结构与状态管理) |
| `frontend/css/style.css` | 430 | 暗色主题样式：响应式布局、卡片悬浮、动画、移动端适配 | [impl](impl/frontend_impl.md#cssstylecss) | [principle](principle/frontend_principle.md#样式系统) |
| `frontend/js/app.js` | 308 | 应用逻辑：API 封装、图片/统计加载、删除/拍照、自动轮询、Toast | [impl](impl/frontend_impl.md#jsappjs) | [principle](principle/frontend_principle.md#前端架构与数据流) |

---

## 5. 数据流概览

### 5.1 图片上传与处理

```
ESP32-CAM (按键或 HTTP 触发)
    │
    ▼  JPEG bytes
Camera.capture() [esp32/ovcam.py:146]
    │
    ▼
_upload_to_server() [esp32/main_app.py:356]
    │ POST /upload (multipart/form-data)
    ▼
upload() [server/routes/api.py:34]
    │
    ▼
save_and_process_image() [server/services/image_service.py:33]
    │
    ├──► 保存原始 → uploads/{uuid}.jpg
    │
    ├──► build_timestamp_text() [server/utils/image_processor.py:122]
    │       └── "自定义文字  |  2024-01-01 12:00:00"
    │
    ├──► add_text_overlay() [server/utils/image_processor.py:21]
    │       ├──► RGBA 转换
    │       ├──► 半透明背景矩形 + 文字
    │       └──► 保存 → processed/{uuid}.jpg
    │
    └──► 可选: 转发到 FORWARD_URL
    │
    ▼
返回 JSON → ESP32
```

### 5.2 MJPEG 实时视频流

```
浏览器请求 http://<esp32-ip>/stream
    │
    ▼
_handle_client() [esp32/main_app.py:260] 路由到 "/stream"
    │
    ▼
_stream_mjpeg() [esp32/main_app.py:203]
    │
    ├──► 发送 multipart/x-mixed-replace 头
    │
    ├──► 循环:
    │       Camera.capture() → JPEG bytes
    │       发送 --boundary 分隔符
    │       发送 Content-Type: image/jpeg
    │       发送 帧数据
    │       time.sleep(0.05)  # 20 fps
    │
    └──► 客户端断开时退出循环
```

### 5.3 前端轮询与交互

```
浏览器加载 http://localhost:8080
    │
    ▼
DOMContentLoaded [frontend/js/app.js:281]
    │
    ├──► loadStats()  ──► GET /api/stats  ──► 更新统计面板
    │
    ├──► loadImages() ──► GET /api/images ──► renderImageGrid()
    │
    └──► startAutoRefresh() [10秒间隔]
            │
            ├──► loadImages() + loadStats()
            │
            └──► 页面 hidden 时暂停，visible 时恢复
```

---

## 6. API 端点速查

### 6.1 ESP32 HTTP API (端口 80)

| 端点 | 方法 | 处理函数 | 说明 |
|------|------|----------|------|
| `/` | GET | JSON 提示 | Web UI 已移至前端 (frontend/) |
| `/config` | GET | JSON 提示 | 配网走 AP 模式 (wificonfig_server.py) |
| `/stream` | GET | `_stream_mjpeg()` | MJPEG 实时视频流 |
| `/capture` | GET | 设置 `capture_flag` | 触发拍照并上传 |
| `/wifi_status` | GET | `wifi_manager.get_status()` | WiFi 状态 JSON |
| `/save_wifi` | POST | `wifi_manager.save_config()` + 重启 | 保存 WiFi 配置 |

### 6.2 服务端 REST API (端口 5000)

| 方法 | 路径 | 处理函数 | 功能 |
|------|------|----------|------|
| POST | `/upload` | `upload()` | 接收 ESP32 上传的图片 |
| GET | `/image/<fn>` | `get_image()` | 获取指定图片文件 |
| GET | `/latest` | `latest()` | 获取最新处理图片 |
| GET | `/api/images` | `api_images()` | JSON 格式图片列表 |
| DELETE | `/api/image/<fn>` | `api_delete_image()` | 删除图片 |
| GET | `/api/stats` | `api_stats()` | JSON 格式统计信息 |
| GET/POST | `/trigger` | `trigger_capture()` | 触发 ESP32 拍照 |

---

## 7. 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 固件 | MicroPython (ESP32-S3) | 固件内置 |
| 后端 | Flask + Flask-CORS | >=2.0, >=4.0 |
| 图片处理 | Pillow | >=9.0 |
| HTTP 请求 | requests | >=2.28 |
| 前端 | 原生 HTML5 + CSS3 + ES6 | - |

---

## 8. 文档导航

- **实现文档**（记载函数在文件第几行）：
  - [ESP32 实现文档](impl/esp32_impl.md)
  - [服务端实现文档](impl/server_impl.md)
  - [前端实现文档](impl/frontend_impl.md)

- **原理文档**（解释模块如何工作）：
  - [ESP32 原理文档](principle/esp32_principle.md)
  - [服务端原理文档](principle/server_principle.md)
  - [前端原理文档](principle/frontend_principle.md)

- **完整使用指南与接口说明**：
  - [docs/README.md](README.md)
