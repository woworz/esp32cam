# ESP32-S3 CAM 公网图传系统

## 1. 当前架构

系统采用“设备主动访问公网服务器”的模型：

```text
浏览器
  │ POST /trigger
  ▼
公网服务器 154.21.201.13
  ├─ Nginx：网页与 API 统一入口（80）
  ├─ Gunicorn + Flask：命令队列、图片 API
  └─ /var/lib/esp-cam：原图、处理图、命令状态
          ▲                    │
          │ POST /upload       │ GET /api/device/commands/next
          │                    ▼
          └──────── ESP32-S3 + OV3660
                       ├─ 每 2 秒主动轮询
                       ├─ 收到 capture 后拍照并上传
                       ├─ 回报 completed/failed
                       └─ GPIO21 仍可本地拍照
```

公网服务器不需要访问设备的局域网 IP，设备也不开放业务端口，因此可穿过普通家庭路由器和 NAT。

## 2. 已删除的旧架构

- 删除 ESP32 日常运行时的 HTTP 服务器。
- 删除板载 `index.html` 控制页。
- 删除 `/stream` MJPEG 实时流、板载 `/capture` 和 `/wifi_status`。
- 删除后端通过 `ESP32_URL` 反向访问局域网设备的逻辑。
- 删除图片接收后的 `FORWARD_URL` 二次转发。
- 删除前端的局域网实时预览卡片和 `localhost:5000` 配置。

`wificonfig_server.py` 被保留：它只在 WiFi 连接失败时临时启动 AP 配网页面，配置成功并重启后即停止。

## 3. 目录结构

```text
esp_cam/
├─ esp32/
│  ├─ boot.py                 启动与首次配网
│  ├─ main_app.py             轮询命令、拍照、上传、结果回报
│  ├─ ovcam.py                OV3660 驱动
│  ├─ tft_display.py          ST7789 驱动
│  ├─ wifimgr.py              WiFi 管理
│  └─ wificonfig_server.py    仅 AP 配网时使用的临时服务器
├─ server/
│  ├─ app.py                  Flask 应用工厂
│  ├─ config.py               环境变量与存储配置
│  ├─ routes/api.py           图片、命令、状态 API
│  ├─ services/
│  │  ├─ command_service.py   持久化命令队列与设备心跳
│  │  └─ image_service.py     图片保存、查询、删除、统计
│  └─ utils/image_processor.py
├─ frontend/                  服务器托管的同源网页
├─ deploy/                    Nginx 与 systemd 生产配置
└─ docs/
```

## 4. 主要数据流

### 远程拍照

1. 浏览器 `POST /trigger`。
2. 服务器创建 `pending` 拍照命令。
3. ESP32 轮询 `/api/device/commands/next` 并领取命令，状态变为 `processing`。
4. ESP32 拍照并 `POST /upload`。
5. 服务器保存原图并生成带时间戳的处理图。
6. ESP32 回报命令 `completed` 或 `failed`。

处理超过 60 秒仍未回报的命令会重新投递，防止设备在领取后断电造成命令永久卡住。

### 本地按键拍照

GPIO21 按下后，ESP32 直接拍照上传；该操作不创建远程命令。

### 设备在线状态

每次命令轮询都会刷新设备 `last_seen`。默认 15 秒未轮询即显示离线。

## 5. 公网 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/upload` | ESP32 上传 JPEG |
| GET | `/image/<filename>` | 获取图片 |
| GET | `/download/<filename>` | 以附件形式下载图片 |
| GET | `/latest` | 获取最新处理图 |
| GET | `/api/images` | 图片列表 |
| DELETE | `/api/image/<filename>` | 删除图片 |
| GET | `/api/stats` | 图片统计、设备在线状态、待执行命令数 |
| POST | `/trigger` | 创建拍照命令 |
| GET | `/api/commands/<id>` | 查询命令执行状态 |
| GET | `/api/device/commands/next?device_id=...` | 设备心跳并领取命令 |
| POST | `/api/device/commands/<id>/result` | 设备回报执行结果 |

## 6. 服务器部署

- 网页入口：`http://154.21.201.13/`
- 应用目录：`/opt/esp-cam`
- 数据目录：`/var/lib/esp-cam`
- 服务：`esp-cam.service`
- 运行模型：Gunicorn 1 worker + 2 threads
- 反向代理：Nginx 监听 80，Gunicorn 仅监听 `127.0.0.1:8000`

生产配置详见 `deploy/README.md`。
