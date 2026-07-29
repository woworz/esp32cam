# 服务端实现

## app.py

`create_app()` 位于 `server/app.py:31`，负责注册 API Blueprint 和创建图片目录。生产环境由 Gunicorn 导入 `app:app`。

## config.py

| 配置 | 默认值/生产值 | 说明 |
|---|---|---|
| `ESP_CAM_HOST` | `0.0.0.0` / `127.0.0.1` | Flask/Gunicorn 监听地址 |
| `ESP_CAM_PORT` | `5000` / `8000` | 应用端口 |
| `ESP_CAM_UPLOAD_FOLDER` | `server/uploads` / `/var/lib/esp-cam/uploads` | 原图目录 |
| `ESP_CAM_PROCESSED_FOLDER` | `server/processed` / `/var/lib/esp-cam/processed` | 处理图目录 |
| `ESP_CAM_COMMAND_STATE_FILE` | `server/commands.json` / `/var/lib/esp-cam/commands.json` | 命令与心跳状态 |
| `ESP_CAM_DEFAULT_DEVICE_ID` | `esp32-s3-cam` | 默认设备 |
| `ESP_CAM_DEVICE_ONLINE_TIMEOUT` | `15` | 在线超时秒数 |
| `ESP_CAM_COMMAND_CLAIM_TIMEOUT` | `60` | 命令重投递秒数 |

旧的 `FORWARD_URL` 和 `ESP32_URL` 已删除。

## routes/api.py

| 函数 | 位置 | 路径 |
|---|---:|---|
| `health()` | 26 | `GET /health` |
| `upload()` | 31 | `POST /upload` |
| `get_image()` | 58 | `GET /image/<filename>` |
| `download_image()` | 67 | `GET /download/<filename>` |
| `latest()` | 81 | `GET /latest` |
| `api_images()` | 89 | `GET /api/images` |
| `api_delete_image()` | 95 | `DELETE /api/image/<filename>` |
| `api_stats()` | 102 | `GET /api/stats` |
| `trigger_capture()` | 109 | `POST /trigger`，只入队，不访问局域网设备 |
| `device_next_command()` | 127 | `GET /api/device/commands/next` |
| `api_command_status()` | 135 | `GET /api/commands/<id>` |
| `device_command_result()` | 147 | `POST /api/device/commands/<id>/result` |

## command_service.py

命令状态存为 JSON，并使用进程内锁与“临时文件 + `os.replace`”原子更新。

状态变化：

```text
pending → processing → completed
                     └→ failed
```

`processing` 超过 60 秒会再次被设备领取。当前生产配置固定为 1 个 Gunicorn worker，因此进程内锁足以保护并发线程。

## image_service.py

`save_and_process_image()` 保存原图，再调用 `image_processor.add_text_overlay()` 生成处理图。服务器就是最终存储位置，不再向其他本地或远程接收端转发。

## 生产进程

```text
Internet :80
  → Nginx（静态前端、上传大小限制、反向代理）
  → Gunicorn 127.0.0.1:8000（1 worker / 2 threads）
  → Flask
```
