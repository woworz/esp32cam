# 轻量生产部署

目标环境为 Debian/Ubuntu，适配 1 核 1G 服务器：

- Nginx 提供静态前端并反向代理 API
- Gunicorn 使用 1 worker + 2 threads
- systemd 管理进程和自动重启
- 图片和设备命令状态持久化在 `/var/lib/esp-cam`，由 systemd
  `StateDirectory` 创建并授权给 `esp-cam` 用户
- 应用代码安装在 `/opt/esp-cam`

部署后的入口：

- 网页：`http://<服务器 IP>/`
- 健康检查：`http://<服务器 IP>/health`
- 图片上传：`POST http://<服务器 IP>/upload`
- 创建拍照命令：`POST http://<服务器 IP>/trigger`
- 设备轮询命令：`GET http://<服务器 IP>/api/device/commands/next?device_id=esp32-s3-cam`

`esp-cam.service` 中的 `ESP_CAM_*` 环境变量可覆盖服务端配置。
