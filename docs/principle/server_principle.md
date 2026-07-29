# 服务端原理

## 公网服务器是唯一业务入口

网页、API、图片和命令状态均位于同一台服务器。Nginx 提供网页并把动态请求转发给 Flask，浏览器不再访问本机 `localhost` 或 ESP32 的局域网 IP。

## 命令队列代替反向访问

浏览器发起远程拍照时，`/trigger` 只创建命令：

```text
浏览器 POST /trigger
  → commands.json 写入 pending
  → ESP32 轮询并领取
  → 状态 processing
  → ESP32 上传图片
  → ESP32 回报 completed/failed
```

服务器不保存也不请求 `ESP32_URL`，因此设备 IP 变化或位于 NAT 后不会影响控制。

## 状态持久化

`commands.json` 同时保存最近 100 条命令和各设备最后心跳。写入先落到 `.tmp` 文件，再使用 `os.replace()` 原子替换，避免进程异常留下半个 JSON 文件。

当前部署使用单 Gunicorn worker、两个线程，进程内 `threading.Lock` 能保护读改写。若未来改成多 worker，应把命令队列迁移到 SQLite 或 Redis。

## 图片存储

- `/var/lib/esp-cam/uploads`：设备上传的原始 JPEG。
- `/var/lib/esp-cam/processed`：叠加时间戳后的 JPEG。
- 图片在公网服务器落地即完成，不再执行二次转发。

## 在线判断

设备每次轮询都会更新 `last_seen`。`/api/stats` 将 15 秒内有心跳的设备标记为在线，同时返回待处理命令数。

## 资源控制

针对 1 核 1G：

- Gunicorn：1 worker + 2 threads；
- systemd `MemoryMax=600M`；
- Nginx 处理静态资源与上传限制；
- Gunicorn 只绑定回环地址。
