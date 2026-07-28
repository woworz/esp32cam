# ESP32 端 - 实现文档

> 本文档记录 ESP32-S3 MicroPython 端每个函数/类的**定义位置**（文件 + 行号），用于快速定位代码。

---

## boot.py

文件：`esp32/boot.py`（49 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `main` | 7 | `main()` | 启动入口。初始化 WiFi，连接失败则进入 AP 配置模式，成功则启动 `main_app.run()` |

---

## main_app.py

文件：`esp32/main_app.py`（419 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `SERVER_URL` | 44 | 模块常量 | Flask 服务端上传地址，必须填写运行服务电脑的局域网 IP |
| `capture_flag` | 45 | 全局变量 | 拍照请求标志（线程间共享） |
| `lock` | 46 | 全局变量 | `_thread.allocate_lock()`，保护 `capture_flag` |
| `_send_response` | 186 | `_send_response(client, status, content_type, body)` | 向 socket 客户端发送 HTTP 响应 |
| `_send_file` | - | `_send_file(client, path, content_type)` | 从板载文件系统以 1024 字节分块发送 `index.html` |
| `_stream_mjpeg` | 203 | `_stream_mjpeg(client)` | **MJPEG 视频流推送**。使用 `multipart/x-mixed-replace`，循环 `camera.capture()` 推送 JPEG 帧，间隔 50ms |
| `_handle_client` | 260 | `_handle_client(client)` | **HTTP 请求路由分发**。解析请求方法/路径，分发到对应处理逻辑 |
| `_upload_to_server` | 356 | `_upload_to_server(buf)` | **图片上传到远程服务器**。使用 `urequests.post` 发送 multipart/form-data |
| `_button_thread` | 402 | `_button_thread()` | **按键监听线程（后台）**。监听 GPIO21，300ms 软件消抖，触发时设置 `capture_flag` |
| `_display_on_tft` | 432 | `_display_on_tft(img_data)` | 将 JPEG 数据显示到 TFT 屏幕（调用 `ST7789.show_jpeg`） |
| `_capture_worker` | 462 | `_capture_worker()` | **拍照任务线程（后台）**。轮询 `capture_flag`，触发时：拍照 → TFT 显示 → 上传 → 清除标志 |
| `run` | 499 | `run()` | **主程序入口**。初始化 WiFi → Camera → TFT → 启动后台线程 → 启动 HTTP 服务器（端口 80） |

---

## ovcam.py

文件：`esp32/ovcam.py`（204 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `FRAMESIZE_QQVGA` | 25 | 类常量 = 0 | 分辨率 96x96 |
| `FRAMESIZE_QVGA` | 26 | 类常量 = 7 | 分辨率 320x240 |
| `FRAMESIZE_VGA` | 27 | 类常量 = 8 | 分辨率 400x296（默认） |
| `FRAMESIZE_SVGA` | 28 | 类常量 = 9 | 分辨率 480x320 |
| `FRAMESIZE_XGA` | 29 | 类常量 = 12 | 分辨率 1024x768 |
| `FRAMESIZE_HD` | 30 | 类常量 = 13 | 分辨率 1280x720 |
| `FRAMESIZE_SXGA` | 31 | 类常量 = 14 | 分辨率 1280x1024 |
| `FRAMESIZE_UXGA` | 32 | 类常量 = 15 | 分辨率 1600x1200 |
| `Camera` | 36 | `class Camera` | OV3660 摄像头控制类 |
| `Camera.__init__` | 74 | `__init__(self, framesize=8, quality=12)` | 构造函数，设置默认分辨率和 JPEG 质量 |
| `Camera.init` | 86 | `init(self)` | **硬件初始化**。配置 DVP 引脚、20MHz XCLK、JPEG/PSRAM、分辨率和质量，调用底层 `camera.init(0, ...)`（首参为 sensor_id，SCCB 使用 `siod`/`sioc`，未接线的 RESET/PWDN 均传 `-1`） |
| `Camera.deinit` | 135 | `deinit(self)` | 释放摄像头硬件资源 |
| `Camera.capture` | 146 | `capture(self) -> bytes` | **拍照**。调用 `camera.capture()` 返回 JPEG bytes，失败返回 `None` |
| `Camera.set_framesize` | 161 | `set_framesize(self, fs)` | 动态修改分辨率（需先 `deinit` 再 `init`） |
| `Camera.set_quality` | 172 | `set_quality(self, q)` | 动态修改 JPEG 质量（0-63，值越小质量越高） |
| `Camera._framesize_name` | 183 | `_framesize_name(self)` | **私有**。根据 `framesize` 值返回分辨率名称字符串 |

---

## wifimgr.py

文件：`esp32/wifimgr.py`（186 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `WiFiManager` | 31 | `class WiFiManager` | WiFi 连接管理器 |
| `WiFiManager.__init__` | 50 | `__init__(self)` | 构造函数。激活 STA 模式，创建 `network.WLAN(network.STA_IF)` |
| `WiFiManager.load_config` | 55 | `load_config(self) -> dict` | 从 `/wifi_config.json` 加载 WiFi 配置 |
| `WiFiManager.save_config` | 70 | `save_config(self, config)` | 保存 WiFi 配置到 `/wifi_config.json` |
| `WiFiManager.scan_networks` | 81 | `scan_networks(self) -> list` | 扫描附近网络，返回 `[{"ssid": str, "rssi": int}]` |
| `WiFiManager.connect` | 100 | `connect(self) -> bool` | **连接 WiFi**。加载配置 → `wlan.connect()` → 15 秒超时 → 返回是否成功 |
| `WiFiManager.start_ap_mode` | 153 | `start_ap_mode(self)` | **启动 AP 热点**。SSID: `ESP32-CAM-Config`，密码: `12345678` |
| `WiFiManager.get_status` | 170 | `get_status(self) -> dict` | 返回 `{"connected": bool, "ssid": str, "ip": str}` |

---

## tft_display.py

文件：`esp32/tft_display.py`（239 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `ST7789.PIN_SCK` | 23 | 类常量 = 39 | SPI 时钟引脚 |
| `ST7789.PIN_SDA` | 24 | 类常量 = 38 | SPI 数据 (MOSI) 引脚 |
| `ST7789.PIN_CS` | 25 | 类常量 = 41 | 片选引脚 |
| `ST7789.PIN_DC` | 26 | 类常量 = 42 | 数据/命令引脚 |
| `ST7789.PIN_RST` | 27 | 类常量 = 47 | 复位引脚 |
| `ST7789.PIN_BL` | 28 | 类常量 = 40 | 背光引脚 |
| `ST7789.WIDTH` | 29 | 类常量 = 320 | 屏幕宽度 |
| `ST7789.HEIGHT` | 30 | 类常量 = 240 | 屏幕高度 |
| `ST7789` | 36 | `class ST7789` | ST7789 TFT 显示屏控制类 |
| `ST7789.__init__` | 60 | `__init__(self)` | 构造函数。初始化 SPI 引脚参数 |
| `ST7789.init` | 68 | `init(self)` | **硬件初始化**。初始化 SPI1@20MHz，发送完整初始化命令序列 |
| `ST7789.deinit` | 128 | `deinit(self)` | 释放 SPI 和引脚资源 |
| `ST7789._write_cmd` | 138 | `_write_cmd(self, cmd)` | **私有**。拉低 DC，发送命令字节 |
| `ST7789._write_data` | 145 | `_write_data(self, data)` | **私有**。拉高 DC，发送数据字节/数组 |
| `ST7789._set_window` | 155 | `_set_window(self, x0, y0, x1, y1)` | **私有**。设置显示窗口（行列地址） |
| `ST7789.fill` | 163 | `fill(self, color)` | 用指定 RGB565 颜色填充整个屏幕 |
| `ST7789.show_image` | 180 | `show_image(self, img_data, x, y, width, height)` | 显示 RGB565 原始图像数据到指定位置 |
| `ST7789.show_jpeg` | 202 | `show_jpeg(self, jpeg_data, x, y)` | 显示 JPEG 图像（需外部解码库转换为 RGB565） |
| `ST7789.set_backlight` | 217 | `set_backlight(self, on)` | 控制背光开关（GPIO 高/低电平） |
| `ST7789.show_text` | 227 | `show_text(self, text, x, y, color=0xFFFF, size=1)` | 在指定位置显示文本（简化位图字体） |

---

## wificonfig_server.py

文件：`esp32/wificonfig_server.py`（199 行）

| 定义 | 行号 | 签名 | 说明 |
|------|------|------|------|
| `_build_html` | 22 | `_build_html(wifi_manager)` | **生成 WiFi 配置页面 HTML**。包含扫描到的网络列表和表单 |
| `_handle_http` | 106 | `_handle_http(client, wifi_manager)` | **处理 HTTP 请求**。路由 `/`（GET 页面）和 `/save`（POST 保存配置） |
| `run` | 169 | `run(wifi_manager, ap)` | **服务器入口**。在 AP 模式下启动 socket 监听（`192.168.4.1:80`），循环接受客户端 |

---

## 模块间调用关系速查

```
boot.py::main()
    │
    ├─→ wifimgr.WiFiManager.__init__()         [wifimgr.py:50]
    │       └─→ network.WLAN(network.STA_IF)
    │
    ├─→ wifimgr.WiFiManager.connect()            [wifimgr.py:100]
    │       └─→ load_config() → wlan.connect()
    │
    ├─→ [失败] wifimgr.WiFiManager.start_ap_mode()  [wifimgr.py:153]
    │   └─→ wificonfig_server.run()              [wificonfig_server.py:169]
    │       └─→ _handle_http() → save_config() → machine.reset()
    │
    └─→ [成功] main_app.run()                    [main_app.py:499]
            │
            ├─→ wifimgr.WiFiManager()            [wifimgr.py:50]
            ├─→ Camera(framesize, quality)        [ovcam.py:74]
            │       └─→ init()                    [ovcam.py:86]
            ├─→ ST7789()                          [tft_display.py:60]
            │       └─→ init()                    [tft_display.py:68]
            ├─→ _thread.start_new_thread(_button_thread, ())   [main_app.py:402]
            ├─→ _thread.start_new_thread(_capture_worker, ())  [main_app.py:462]
            └─→ socket server (port 80)
                    └─→ _handle_client()         [main_app.py:260]
                            ├─→ "/"           → JSON 提示(已移至前端)        
                            ├─→ "/config"     → JSON 提示(配网走 AP 模式)     
                            ├─→ "/stream"     → _stream_mjpeg()         [main_app.py:203]
                            ├─→ "/capture"    → 设置 capture_flag
                            ├─→ "/wifi_status"→ wifi_manager.get_status() [wifimgr.py:170]
                            └─→ POST "/save_wifi" → save_config() → machine.reset() [wifimgr.py:70]
```
