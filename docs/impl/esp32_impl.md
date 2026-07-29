# ESP32 端实现

## boot.py

| 定义 | 位置 | 说明 |
|---|---:|---|
| `main()` | `boot.py:7` | 连接已保存 WiFi；失败时启动临时 AP 配网，成功后进入 `main_app.run()` |

## main_app.py

| 定义 | 位置 | 说明 |
|---|---:|---|
| `DEVICE_ID` | 25 | 服务器识别设备的固定 ID |
| `SERVER_BASE_URL` | 26 | 公网服务器地址 `http://154.21.201.13` |
| `COMMAND_POLL_INTERVAL_MS` | 34 | 命令轮询周期，默认 2 秒 |
| `_upload_to_server()` | 50 | multipart 上传 JPEG、标识文字和设备 ID |
| `_poll_remote_command()` | 94 | 领取服务器队列中的下一条命令，同时刷新心跳 |
| `_report_command_result()` | 114 | 回报 `completed` 或 `failed` |
| `_display_on_tft()` | 145 | 显示照片或拍照状态 |
| `_capture_and_upload()` | 169 | 拍照、显示、上传的统一流程 |
| `_ensure_wifi()` | 187 | 断线时尝试重新连接 |
| `run()` | 195 | 初始化 Camera/TFT/GPIO，运行按键检测与命令轮询主循环 |

日常运行不导入 `socket`、不创建 `_thread`，也不监听任何 TCP 端口。

## WiFi 相关模块

- `wifimgr.py`：保存配置、STA 连接、扫描网络、启动 AP。
- `wificonfig_server.py`：只在 STA 连接失败时监听 `192.168.4.1:80`，保存 WiFi 后重启。
- 配网服务不是图传或远程控制服务器，正常联网运行时不会启动。

## 已删除文件和入口

- `esp32/index.html`
- 板载 `/`、`/capture`、`/stream`、`/wifi_status`
- MJPEG 推流和 socket accept 循环
- 拍照线程、流线程及摄像头互斥锁

## 主循环

```text
初始化 WiFi/Camera/TFT/GPIO
  └─ 循环
      ├─ 检测 GPIO21 下降沿 → 拍照上传
      ├─ 每 2 秒检查 WiFi
      ├─ GET 下一条云端命令
      ├─ capture → 拍照上传
      └─ POST 执行结果
```
