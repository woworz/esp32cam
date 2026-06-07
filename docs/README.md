# ESP32-S3 CAM 图传系统 - 软件文档

## 1. 项目概述

本项目是一个基于 **ESP32-S3 + OV3660 + ST7789 TFT** 的无线图传系统，支持:
- MJPEG 实时视频流
- 按键/HTTP 触发拍照
- 照片上传到远程服务器
- 服务器端自动叠加文字时间戳
- **1.8寸 TFT 彩屏实时显示**
- 可视化 Web 后端界面
- 远程触发拍照

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      ESP32-S3 端                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ OV3660   │  │ WiFi     │  │ HTTP Server (80)     │  │
│  │ 摄像头   │──│ Manager  │──│ - MJPEG 视频流       │  │
│  └──────────┘  └──────────┘  │ - 拍照上传           │  │
│       │                      │ - WiFi 配置页面      │  │
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

## 2. 硬件连接

### ESP32-S3-DevKitC-1 <-> OV3660 引脚映射

| 功能     | OV3660引脚 | ESP32-S3 GPIO | 说明                    |
|----------|-----------|---------------|------------------------|
| 数据位0  | D0        | GPIO11        | 并行数据线              |
| 数据位1  | D1        | GPIO9         | 并行数据线              |
| 数据位2  | D2        | GPIO8         | 并行数据线              |
| 数据位3  | D3        | GPIO10        | 并行数据线              |
| 数据位4  | D4        | GPIO12        | 并行数据线              |
| 数据位5  | D5        | GPIO18        | 并行数据线              |
| 数据位6  | D6        | GPIO17        | 并行数据线              |
| 数据位7  | D7        | GPIO16        | 并行数据线              |
| 时钟输出 | XCLK      | GPIO15        | ESP32为OV3660提供时钟   |
| 像素时钟 | PCLK      | GPIO13        | 每个时钟传输一个像素     |
| 垂直同步 | VSYNC     | GPIO6         | 标识一帧开始            |
| 水平参考 | HREF      | GPIO7         | 标识一行有效像素         |
| I2C数据  | SIOD      | GPIO4         | SCCB配置接口 (SDA)      |
| I2C时钟  | SIOC      | GPIO5         | SCCB配置接口 (SCL)      |
| 复位     | RESET     | GPIO14        | 低电平复位              |
| 掉电     | PWDN      | GND           | 直接接地，摄像头常开     |

### 其他引脚使用

| 功能              | GPIO    | 说明                          |
|------------------|---------|-------------------------------|
| CH340C 串口      | GPIO43, GPIO44 | USB 串口通信 (TXD/RXD)  |
| USB-OTG          | GPIO19, GPIO20 | USB D-/D+                   |
| WS2812B RGB LED  | GPIO48  | 板载 RGB 灯珠                 |
| 复位按键 (EN)    | EN      | 硬件复位                      |
| BOOT 按键        | GPIO0   | 下载模式，带自动下载电路      |
| 拍照按键 (可选)  | GPIO21  | 上拉输入，按下接地            |

### TFT 显示屏连接 (1.8寸 ST7789 240x320)

| 功能      | TFT引脚 | ESP32-S3 GPIO | 说明                     |
|-----------|---------|---------------|--------------------------|
| SPI 时钟  | SCK     | GPIO39        | SPI 时钟线               |
| SPI 数据  | SDA     | GPIO38        | SPI MOSI 数据线          |
| 片选      | CS      | GPIO37        | SPI 片选 (低电平有效)    |
| 数据/命令 | DC      | GPIO36        | 高电平=数据, 低电平=命令 |
| 复位      | RST     | GPIO35        | 低电平复位               |
| 背光      | BL      | GPIO40        | 高电平开启背光           |
| 电源正极  | VCC     | 3.3V          | **必须接3.3V! 不要接5V** |
| 电源负极  | GND     | GND           | 接地                     |

---

## 3. 文件结构

```
esp_cam/
├── esp32/                    # ESP32-S3 MicroPython 端
│   ├── boot.py               # 启动脚本 (Thonny 自动执行)
│   ├── main_app.py           # 主程序 (HTTP服务器 + 拍照上传)
│   ├── camera.py             # OV3660 摄像头驱动封装
│   ├── tft_display.py        # ST7789 TFT 显示屏驱动封装
│   ├── wifimgr.py            # WiFi 连接管理
│   ├── wificonfig_server.py  # AP模式配置服务器
│   └── wifi_config.json      # WiFi 配置文件 (运行时生成)
│
├── server/                   # PC/后端 API 服务端
│   ├── app.py                # Flask 应用工厂
│   ├── config.py             # 配置文件
│   ├── requirements.txt      # Python 依赖
│   ├── uploads/              # 原始上传图片 (运行时生成)
│   ├── processed/            # 处理后图片 (运行时生成)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── api.py            # API 路由 Blueprint
│   ├── services/
│   │   ├── __init__.py
│   │   └── image_service.py  # 图片业务逻辑层
│   └── utils/
│       ├── __init__.py
│       └── image_processor.py # 图片处理工具
│
├── frontend/                 # 前端 SPA 应用
│   ├── index.html            # 主页面
│   ├── css/
│   │   └── style.css         # 样式文件
│   ├── js/
│   │   └── app.js            # 前端逻辑
│   └── README.md             # 前端说明文档
│
└── docs/
    └── README.md             # 本文档
```

---

## 4. 模块接口说明

### 4.1 ESP32 端模块

#### `camera.py` - Camera 类

```python
class Camera:
    """OV3660 摄像头控制类"""

    # 分辨率常量
    FRAMESIZE_QQVGA = 0    # 96x96
    FRAMESIZE_QVGA = 7     # 320x240
    FRAMESIZE_VGA = 8      # 400x296 (默认)
    FRAMESIZE_SVGA = 9     # 480x320
    FRAMESIZE_XGA = 12     # 1024x768
    FRAMESIZE_HD = 13      # 1280x720
    FRAMESIZE_SXGA = 14    # 1280x1024
    FRAMESIZE_UXGA = 15    # 1600x1200

    def __init__(self, framesize=8, quality=12):
        """
        参数:
            framesize (int): 分辨率，使用 FRAMESIZE_* 常量
            quality (int): JPEG质量，0-63，值越小质量越高
        """

    def init(self):
        """初始化摄像头硬件，失败抛出异常"""

    def deinit(self):
        """释放摄像头资源"""

    def capture(self) -> bytes:
        """拍照，返回 JPEG 数据 (bytes)，失败返回 None"""

    def set_framesize(self, fs):
        """动态修改分辨率"""

    def set_quality(self, q):
        """动态修改 JPEG 质量"""
```

#### `wifimgr.py` - WiFiManager 类

```python
class WiFiManager:
    """WiFi 连接管理器"""

    def __init__(self):
        """初始化 WiFi，激活 STA 模式"""

    def load_config(self) -> dict:
        """从 /wifi_config.json 加载配置"""

    def save_config(self, config: dict):
        """保存配置到 /wifi_config.json"""

    def scan_networks(self) -> list:
        """扫描附近网络，返回 [{"ssid": str, "rssi": int, "channel": int}]"""

    def connect(self) -> bool:
        """连接 WiFi，超时15秒，返回是否成功"""

    def start_ap_mode(self) -> network.WLAN:
        """启动 AP 热点 (ESP32-CAM-Config / 12345678)"""

    def get_status(self) -> dict:
        """返回 {"connected": bool, "ssid": str, "ip": str}"""
```

#### `main_app.py` - 全局函数

```python
def run():
    """
    主程序入口

    执行流程:
        1. 初始化 WiFi 连接
        2. 初始化摄像头 (VGA, quality=12)
        3. 初始化 TFT 显示屏
        4. 启动按键监听线程 (GPIO21)
        5. 启动拍照任务线程
        6. 启动 HTTP 服务器 (端口80)

    使用:
        >>> import main_app
        >>> main_app.run()
    """
```

#### `tft_display.py` - ST7789 类

```python
class ST7789:
    """ST7789 TFT 显示屏控制类 (240x320)"""

    # 引脚配置
    PIN_SCK = 39    # SPI 时钟
    PIN_SDA = 38    # SPI 数据 (MOSI)
    PIN_CS = 37     # 片选
    PIN_DC = 36     # 数据/命令
    PIN_RST = 35    # 复位
    PIN_BL = 40     # 背光

    def __init__(self):
        """初始化显示屏参数"""

    def init(self):
        """初始化硬件，发送初始化命令序列"""

    def deinit(self):
        """释放硬件资源"""

    def fill(self, color: int):
        """用指定颜色填充整个屏幕 (RGB565)"""

    def show_image(self, img_data: bytes, x: int, y: int, width: int, height: int):
        """在指定位置显示图像"""

    def show_text(self, text: str, x: int, y: int, color: int = 0xFFFF, size: int = 1):
        """在指定位置显示文本"""

    def set_backlight(self, on: bool):
        """控制背光开关"""
```

#### `wificonfig_server.py` - 全局函数

```python
def run(wifi_manager, ap):
    """
    启动 WiFi 配置服务器 (AP模式)

    参数:
        wifi_manager (WiFiManager): WiFi管理器实例
        ap: AP接口对象

    使用:
        wm = WiFiManager()
        ap = wm.start_ap_mode()
        wificonfig_server.run(wm, ap)
    """
```

### 4.2 服务端模块

#### `app.py` - 应用工厂

使用 Flask Application Factory 模式创建应用实例:

```python
def create_app(config_name='default'):
    """
    应用工厂函数

    功能:
        1. 创建 Flask 应用实例
        2. 加载配置文件
        3. 注册 API Blueprint
        4. 初始化 CORS 跨域支持
        5. 创建上传目录

    返回:
        Flask app 实例
    """
```

#### `routes/api.py` - API 路由 Blueprint

所有 API 端点通过 Flask Blueprint 注册:

```python
from flask import Blueprint

api_bp = Blueprint('api', __name__)

# 注册的路由:
# POST /upload        -> 接收ESP32上传的图片
# GET  /image/<fn>    -> 获取指定图片
# GET  /latest        -> 获取最新处理后的图片
# GET  /api/images    -> 图片列表 (JSON)
# GET  /api/stats     -> 系统统计 (JSON)
# DELETE /api/image/<fn> -> 删除图片
# GET|POST /trigger   -> 远程触发ESP32拍照
```

#### `services/image_service.py` - 图片业务逻辑

```python
def save_upload(file_storage, text="") -> dict:
    """
    保存上传的图片并处理

    参数:
        file_storage: Flask FileStorage 对象
        text: 叠加文字

    返回:
        {"raw": str, "processed": str, "text": str}
    """

def get_image_list() -> list:
    """获取所有已处理图片列表，按时间倒序"""

def get_stats() -> dict:
    """获取系统统计信息"""

def delete_image(filename: str) -> bool:
    """删除指定图片 (原始 + 处理后)"""

def get_latest_image() -> str:
    """返回最新处理后图片的路径"""
```

#### API 路由表

| 路由                  | 方法       | 功能                          |
|----------------------|------------|-------------------------------|
| `POST /upload`       | POST       | 接收ESP32上传的图片           |
| `GET /image/<fn>`    | GET        | 获取指定图片                  |
| `GET /latest`        | GET        | 获取最新处理后的图片          |
| `GET /api/images`    | GET        | 图片列表 (JSON)               |
| `GET /api/stats`     | GET        | 系统统计 (JSON)               |
| `DELETE /api/image/<fn>` | DELETE | 删除图片                      |
| `GET|POST /trigger`  | GET/POST   | 远程触发ESP32拍照             |

#### `/upload` 接口详细说明

**请求:**
```
POST /upload HTTP/1.1
Content-Type: multipart/form-data; boundary=----ESP32Boundary

------ESP32Boundary
Content-Disposition: form-data; name="image"; filename="capture.jpg"
Content-Type: image/jpeg

[JPEG 二进制数据]
------ESP32Boundary
Content-Disposition: form-data; name="text"

ESP32-S3 CAM
------ESP32Boundary--
```

**响应:**
```json
{
    "status": "ok",
    "message": "上传成功",
    "raw": "a1b2c3d4.jpg",
    "processed": "e5f6a7b8.jpg",
    "text": "ESP32-S3 CAM  |  2024-01-01 12:00:00"
}
```

#### `config.py` - 配置项

| 配置项            | 默认值                | 说明                    |
|------------------|----------------------|------------------------|
| HOST             | `"0.0.0.0"`          | 监听地址               |
| PORT             | `5000`               | 监听端口               |
| UPLOAD_FOLDER    | `"uploads"`          | 原始图片目录           |
| PROCESSED_FOLDER | `"processed"`        | 处理后图片目录         |
| FORWARD_URL      | `None`               | 转发目标URL            |
| ESP32_URL        | `None`               | ESP32拍照触发地址      |
| FONT_PATH        | `None`               | 自定义字体路径         |
| TEXT_POSITION    | `"bottom"`           | 文字位置               |
| TEXT_COLOR       | `(255, 255, 255)`    | 文字颜色 (白色)        |
| TEXT_BG_COLOR    | `(0, 0, 0, 128)`     | 背景色 (半透明黑)      |
| CORS_ORIGINS     | `["*"]`              | 允许的跨域来源         |

#### `image_processor.py` - 图片处理

```python
def add_text_overlay(
    image_path: str,      # 原图路径
    text: str,            # 叠加文字
    output_path: str,     # 输出路径
    position: str = "bottom",  # 位置: "top"/"bottom"/"center"
    text_color: tuple = (255, 255, 255),  # 文字颜色
    bg_color: tuple = (0, 0, 0, 128),     # 背景色
    font_path: str = None,                 # 字体路径
) -> str:
    """叠加文字到图片，返回输出路径"""

def build_timestamp_text(custom_text: str = "") -> str:
    """构建时间戳文字，如 "ESP32  |  2024-01-01 12:00:00" """
```

---

## 5. 使用指南

### 5.1 首次配置 WiFi

#### 方法一: 通过 AP 热点配置

1. 在 Thonny 中运行:
   ```python
   from wifimgr import WiFiManager
   from wificonfig_server import run
   
   wm = WiFiManager()
   ap = wm.start_ap_mode()
   run(wm, ap)
   ```

2. 手机/电脑连接 WiFi: **ESP32-CAM-Config** (密码: 12345678)

3. 浏览器访问 **http://192.168.4.1**

4. 选择你的 WiFi 并输入密码，点击"保存并连接"

5. ESP32-S3 自动重启并连接 WiFi

#### 方法二: 手动编辑配置文件

1. 通过 Thonny 将以下内容写入 `/wifi_config.json`:
   ```json
   {
       "ssid": "你的WiFi名称",
       "password": "你的WiFi密码",
       "static_ip": "",
       "subnet_mask": "",
       "gateway": ""
   }
   ```

2. 重启 ESP32-S3

### 5.2 运行主程序

WiFi 配置完成后，在 Thonny 中运行:

```python
import main_app
main_app.run()
```

启动成功后会显示:
```
[WiFi] 连接成功!
  IP:    192.168.1.xxx
[Camera] 初始化成功 (分辨率:400x296 质量:12)
[HTTP] 服务器已启动 -> http://192.168.1.xxx
```

### 5.3 访问 Web 界面

在浏览器中输入 ESP32-S3 的 IP 地址:

- **http://192.168.1.xxx/** - 主控页面 (实时视频流 + 拍照按钮)
- **http://192.168.1.xxx/config** - WiFi 配置页面
- **http://192.168.1.xxx/stream** - MJPEG 视频流地址
- **http://192.168.1.xxx/capture** - 触发拍照上传 (HTTP GET)
- **http://192.168.1.xxx/wifi_status** - WiFi 状态查询 (JSON)

### 5.4 启动服务端

#### 启动后端 API 服务

在 PC 上:

```bash
cd server
pip install -r requirements.txt
python app.py
```

后端服务启动后:
- API 服务运行在 **http://localhost:5000/**
- ESP32 拍照后会自动上传到此服务端

#### 启动前端应用

在另一个终端窗口:

```bash
cd frontend
python -m http.server 8080
```

前端启动后:
- 访问 **http://localhost:8080** 查看照片画廊和远程控制界面
- 前端通过 CORS 调用后端 API (默认端口 5000)

### 5.5 配置服务端

编辑 `server/config.py`:

```python
# 设置 ESP32 的拍照触发地址 (实现远程触发)
ESP32_URL = "http://192.168.1.xxx/capture"

# 设置图片转发地址 (可选)
FORWARD_URL = "http://另一台服务器:5000/upload"

# 自定义中文字体 (解决中文显示乱码)
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
```

---

## 6. API 参考

### 6.1 ESP32 HTTP API

| 端点          | 方法 | 说明              | 响应格式    |
|--------------|------|-------------------|-------------|
| `/`          | GET  | 主控页面          | HTML        |
| `/config`    | GET  | WiFi配置页面      | HTML        |
| `/stream`    | GET  | MJPEG实时视频流   | multipart   |
| `/capture`   | GET  | 触发拍照上传      | JSON        |
| `/wifi_status`| GET | WiFi状态          | JSON        |
| `/save_wifi` | POST | 保存WiFi配置      | JSON        |

### 6.2 服务端 API

| 端点                  | 方法     | 说明                | 请求格式         | 响应格式 |
|----------------------|----------|--------------------|-----------------|----------|
| `/upload`            | POST     | 上传图片           | multipart/form  | JSON     |
| `/image/<fn>`        | GET      | 获取图片           | -               | image/*  |
| `/latest`            | GET      | 获取最新图片       | -               | image/*  |
| `/api/images`        | GET      | 图片列表           | -               | JSON     |
| `/api/stats`         | GET      | 系统统计           | -               | JSON     |
| `/api/image/<fn>`    | DELETE   | 删除图片           | -               | JSON     |
| `/trigger`           | GET/POST | 远程触发拍照       | -               | JSON     |

#### `GET /api/images` 响应格式

```json
{
    "status": "ok",
    "count": 2,
    "images": [
        {
            "filename": "e5f6a7b8.jpg",
            "size": 12345,
            "created": "2024-01-01T12:00:00",
            "url": "/image/e5f6a7b8.jpg"
        }
    ]
}
```

#### `GET /api/stats` 响应格式

```json
{
    "status": "ok",
    "stats": {
        "processed_count": 10,
        "raw_count": 5,
        "total_size": 1024000,
        "esp32_configured": true,
        "esp32_url": "http://192.168.1.xxx/capture"
    }
}
```
#### `DELETE /api/image/<fn>` 响应格式

```json
{
    "status": "ok",
    "message": "删除成功"
}
```

---

## 7. 常见问题

### Q: 摄像头初始化失败?
A: 检查:
1. 排线连接是否牢固
2. OV3660 是否支持 DVP 接口
3. XCLK 引脚是否正确连接到 GPIO15
4. PWDN 是否接 GND

### Q: WiFi 连接失败?
A: 检查:
1. SSID 和密码是否正确
2. 路由器是否在 2.4GHz 频段 (ESP32-S3 不支持 5GHz)
3. 信号强度是否足够

### Q: 图片上传失败?
A: 检查:
1. 服务端是否已启动
2. `main_app.py` 中的 `SERVER_URL` 是否正确
3. ESP32 和 PC 是否在同一局域网

### Q: 视频流卡顿?
A: 可能原因:
1. 分辨率过高，降低到 VGA 或 QVGA
2. WiFi 信号弱
3. 调大 `_stream_mjpeg()` 中的 `time.sleep()` 值

### Q: 中文显示为方块?
A: 在 `server/config.py` 中设置中文字体路径:
```python
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"  # Windows
# 或
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"  # Linux
```

### Q: TFT 显示屏无显示?
A: 检查:
1. VCC 是否接 3.3V (不要接 5V!)
2. SPI 引脚连接是否正确
3. 背光引脚 BL 是否接高电平
4. 是否安装了正确的 MicroPython 固件

### Q: TFT 显示屏颜色异常?
A: 检查:
1. ST7789 初始化命令是否正确
2. RGB565 格式是否匹配
3. 尝试调整 `CMD_MADCTL` 值 (横屏/竖屏)

---

## 8. 依赖清单

### ESP32 端 (MicroPython 固件自带)
- camera (ESP32-S3 固件内置)
- network
- socket
- machine
- _thread
- json
- urequests (需手动上传到板子)

### 服务端
```
flask>=2.0
flask-cors>=4.0
Pillow>=9.0
requests>=2.28
```

安装: `pip install -r requirements.txt`

### 可选依赖
- `jpegdecoder` - JPEG 解码库 (用于 TFT 显示 JPEG 图像)
