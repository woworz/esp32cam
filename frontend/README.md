# ESP32-CAM 公网控制前端

该目录是由公网服务器 Nginx 托管的原生 HTML/CSS/JS 单页应用。

## 功能

- 展示设备在线状态和最后心跳；
- 创建远程拍照命令；
- 显示图片数量、存储大小和待执行命令；
- 浏览、刷新和删除服务器图片。
- 下载服务器中的单张照片。

## 运行方式

生产入口：

```text
http://154.21.201.13/
```

前端与 API 同源，`js/app.js` 中的 `API_BASE_URL` 为空字符串，不需要单独启动 `localhost:8080`，也不需要配置本地 Flask 地址。

## API

| 路径 | 方法 | 用途 |
|---|---|---|
| `/api/stats` | GET | 图片和设备状态 |
| `/api/images` | GET | 图片列表 |
| `/api/image/<filename>` | DELETE | 删除图片 |
| `/download/<filename>` | GET | 下载图片附件 |
| `/trigger` | POST | 创建远程拍照命令 |
| `/api/commands/<id>` | GET | 查询拍照命令结果 |

ESP32 的命令轮询和上传接口由后端提供，浏览器不会直接访问设备。
