# 前端原理

## 同源架构

浏览器只访问 `http://154.21.201.13/`。网页和 API 均由 Nginx 暴露，因此 Fetch 使用相对路径，不需要硬编码 `localhost:5000` 或开启局域网跨域访问。

## 远程拍照不是直连设备

按钮点击后发送 `POST /trigger`。HTTP 202 表示命令已进入队列，并不表示照片已经产生。ESP32 在下一次轮询领取命令，上传完成后画廊才出现新图片。

## 状态展示

`GET /api/stats` 提供：

- `device_online`：设备是否在心跳窗口内；
- `device_last_seen`：最后轮询时间；
- `pending_commands`：等待或正在执行的命令数；
- 图片数量和存储大小。

网页每 10 秒刷新；命令入队后额外延迟 3 秒刷新一次。

## 图片画廊

`GET /api/images` 返回按时间倒序的处理图。图片地址使用同源 `/image/<filename>`。删除操作通过 `DELETE /api/image/<filename>` 完成。

## 已移除能力

前端不再嵌入板载 MJPEG、不显示“打开全屏流”，也不会从 `ESP32_URL` 推导 `/stream` 地址。远程预览当前以服务器中的最新照片和画廊为准。
