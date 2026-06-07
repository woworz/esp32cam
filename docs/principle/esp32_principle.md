# ESP32 端 - 原理文档

> 本文档解释 ESP32-S3 MicroPython 端各模块的**工作原理**、**设计思路**和**关键机制**。

---

## 启动流程

### 1. 上电 → boot.py

MicroPython 固件上电后，自动按顺序执行：
1. `boot.py`（如果存在）
2. `main.py`（如果存在）

本项目将启动逻辑放在 `boot.py` 的 `main()` 函数中，上电后调用该函数。

### 2. WiFi 连接尝试

`main()` 的执行路径是一个**分支决策树**：

```
上电
  │
  ▼
WiFiManager() ──→ connect() ──→ 15秒超时等待
  │
  ├─→ [成功] 获取 IP → 启动 main_app.run()
  │
  └─→ [失败] 启动 AP 配置模式
          │
          ▼
      start_ap_mode()  (热点: ESP32-CAM-Config / 12345678)
          │
          ▼
      wificonfig_server.run()  (监听 192.168.4.1:80)
          │
          ▼
      用户连接热点 → 浏览器访问 192.168.4.1
          │
          ▼
      选择 WiFi + 输入密码 → POST /save
          │
          ▼
      save_config() → machine.reset()  (重启，回到顶部)
```

**设计意图**：设备首次使用时无需预写配置文件，直接通过手机配置即可联网。配置错误时自动回到 AP 模式，无限重试直到成功。

---

## 主程序与线程模型

### 多线程架构

`main_app.run()` 启动后，系统运行在**一个主线程 + 两个后台线程**的模型下：

| 线程 | 函数 | 优先级 | 职责 |
|------|------|--------|------|
| 主线程 | `run()` → socket accept 循环 | 主 | HTTP 服务器监听和请求处理 |
| 后台线程 1 | `_button_thread()` | 低 | 监听 GPIO21 按键，300ms 消抖 |
| 后台线程 2 | `_capture_worker()` | 低 | 轮询拍照标志，执行拍照 → 显示 → 上传 |

### 线程同步机制

两个后台线程通过**共享标志 + 互斥锁**进行同步：

```python
capture_flag = False          # 全局标志：是否触发拍照
lock = _thread.allocate_lock()  # 互斥锁，保护 capture_flag
```

- **生产者**（`_button_thread`）：检测到按键按下 → `lock.acquire()` → `capture_flag = True` → `lock.release()`
- **消费者**（`_capture_worker`）：`lock.acquire()` → 检查 `capture_flag` → 若为 `True`，执行拍照流程 → `capture_flag = False` → `lock.release()`

**为什么不用队列？** ESP32 的 MicroPython  `_thread` 模块标准库中无 Queue，使用原子标志是最轻量的方案。

### HTTP 服务器设计

采用**原始 socket + 多线程**实现，而非 `uasyncio` 或 `microWebSrv`：

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('0.0.0.0', 80))
sock.listen(5)

while True:
    client, addr = sock.accept()
    _thread.start_new_thread(_handle_client, (client,))
```

每个客户端连接创建一个独立线程处理，简化并发逻辑，但受限于 ESP32-S3 的 512KB SRAM，**并发连接数有限**（默认 `listen(5)` 即最多 5 个排队连接）。

---

## MJPEG 视频流

### 协议基础

MJPEG over HTTP 使用 **`multipart/x-mixed-replace`** MIME 类型：

```
HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace; boundary=--esp32-boundary

--esp32-boundary
Content-Type: image/jpeg
Content-Length: 12345

[JPEG 二进制数据]
--esp32-boundary
Content-Type: image/jpeg
...
```

浏览器遇到该 Content-Type 时会：**显示第一帧 → 遇到 boundary → 替换为下一帧 → 循环**

### 实现细节

`_stream_mjpeg()` 的核心循环：

```python
while True:
    frame = camera_obj.capture()   # 获取 JPEG 帧
    if not frame:
        break
    
    # 发送 boundary 分隔符 + 帧头 + 帧数据
    client.send(b"--esp32-boundary\r\n")
    client.send(b"Content-Type: image/jpeg\r\n")
    client.send(f"Content-Length: {len(frame)}\r\n\r\n".encode())
    client.send(frame)
    
    time.sleep(0.05)  # 50ms ≈ 20 fps
```

**帧率控制**：`time.sleep(0.05)` 将帧率限制在约 20fps。若删除此 sleep，受限于 `camera.capture()` 的硬件速度和 JPEG 编码时间，实际帧率约为 15-25fps（VGA 分辨率下）。

**带宽估算**：VGA 质量 12 的 JPEG 约为 15-25KB/帧，20fps 时约 **300-500KB/s ≈ 2.4-4Mbps**，在良好 WiFi 信号下可流畅传输。

---

## 摄像头驱动

### OV3660 DVP 接口

OV3660 使用 **8 位并行 DVP（Digital Video Port）** 接口：

| 信号 | 功能 |
|------|------|
| D0-D7 | 8 位像素数据 |
| XCLK | ESP32 提供的时钟（24MHz） |
| PCLK | 像素时钟（每时钟传输一个像素） |
| VSYNC | 帧同步（标识新一帧开始） |
| HREF | 行同步（标识一行有效像素） |
| SIOD/SIOC | SCCB（I2C）配置接口 |

`camera.init()` 在底层完成：
1. 配置 ESP32-S3 的 LCD_CAM 外设为 8 位并行模式
2. 通过 SCCB 向 OV3660 写入初始化寄存器序列
3. 设置分辨率、格式、帧率等参数

### 分辨率与质量权衡

| 分辨率 | 像素 | 单帧大小 | 适用场景 |
|--------|------|----------|----------|
| QQVGA (0) | 96x96 | ~3KB | 极小预览 |
| QVGA (7) | 320x240 | ~8KB | 低带宽流 |
| **VGA (8)** | 400x296 | ~15KB | **默认平衡** |
| SVGA (9) | 480x320 | ~20KB | 中等质量 |
| XGA (12) | 1024x768 | ~50KB | 高分辨率 |
| HD (13) | 1280x720 | ~60KB | 高清流 |
| UXGA (15) | 1600x1200 | ~120KB | 拍照上传 |

**默认使用 VGA (8) + quality=12**：在 MJPEG 流流畅性和图片清晰度之间取得平衡。quality 值越小 JPEG 质量越高（文件越大），范围 0-63。

---

## 显示屏驱动

### ST7789 SPI 协议

ST7789 使用 **4 线 SPI** 通信：

| 线 | 功能 |
|----|------|
| SCK | 时钟（ESP32 提供，40MHz） |
| SDA (MOSI) | 数据（ESP32 → 屏幕） |
| CS | 片选（低电平有效） |
| DC | 数据/命令选择（低=命令，高=数据） |
| RST | 硬件复位 |

### 初始化序列

`ST7789.init()` 发送一系列命令配置显示屏：

```
SWRESET (软件复位) → SLPOUT (退出睡眠) →
MADCTL (扫描方向: MX+MV+MY 横屏) →
COLMOD (16位色 RGB565) →
PORCTRL ( porch 设置 ) → ... → DISPON (显示开启)
```

**MADCTL 值 0xA0**：设置 `MX=1, MV=1, MY=0`，即**横屏显示**，坐标原点在左上角。

### RGB565 像素格式

每个像素占 2 字节（16 位）：`RRRRR GGGGGG BBBBB`（5-6-5 分布）

`fill()` 和 `show_image()` 均以 RGB565 格式操作。`show_jpeg()` 需外部库将 JPEG 解码为 RGB565 后再写入。

---

## Wi-Fi 管理

### STA 模式连接流程

```
WiFiManager()
  │
  ▼
STA_IF.active(True)           # 激活 STA 接口
  │
  ▼
load_config() ──→ /wifi_config.json
  │
  ▼
scan_networks() ──→ 可选：让用户选择网络
  │
  ▼
connect(ssid, password)
  │
  ├──→ wlan.connect(ssid, password)
  ├──→ 循环检查 wlan.isconnected()，最多 15 秒
  ├──→ [成功] 打印 IP，返回 True
  └──→ [失败] 打印错误，返回 False
```

### AP 模式配置服务器

当 STA 连接失败时，系统切换到 AP 模式：

```
start_ap_mode()
  │
  ├──→ AP_IF.active(True)
  ├──→ AP_IF.config(essid='ESP32-CAM-Config', password='12345678', authmode=3)
  └──→ 返回 AP 接口对象

wificonfig_server.run(wifi_manager, ap)
  │
  ├──→ socket.bind(('192.168.4.1', 80))
  ├──→ 循环 accept()
  └──→ _handle_http()
          │
          ├─→ GET / → _build_html() 返回配置页面（含扫描到的 WiFi 列表）
          └─→ POST /save → save_config() → machine.reset()
```

**安全设计**：AP 密码固定为 `12345678`，仅用于首次配置。配置完成后设备重启进入 STA 模式，AP 关闭。

---

## AP 配置服务器

### HTML 页面生成

`_build_html()` 动态生成包含 WiFi 扫描结果的 HTML 表单：

```python
networks = wifi_manager.scan_networks()
options = "\n".join(
    f'<option value="{n["ssid"]}">{n["ssid"]} (信号:{n["rssi"]}dBm)</option>'
    for n in networks
)
```

页面包含：
- 下拉选择框（扫描到的网络，按信号强度排序）
- 密码输入框
- 保存按钮 → POST `/save`

### 配置保存与重启

收到 POST 请求后：
1. 解析表单数据（`ssid` 和 `password`）
2. 调用 `wifi_manager.save_config({"ssid": ssid, "password": password})`
3. 写入 `/wifi_config.json`
4. 调用 `machine.reset()` 重启设备
5. 重启后 `boot.py` 读取新配置，尝试连接

**为什么用重启而非热切换？** MicroPython 的 `network.WLAN` 在 STA 和 AP 模式间切换时可能出现状态残留，重启是最可靠的恢复方式。
