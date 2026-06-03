"""
main_app.py - ESP32-S3 CAM 主程序

本模块是 ESP32-S3 的核心运行程序，提供以下功能:
    1. HTTP 服务器 - 提供 Web 控制界面和 MJPEG 实时视频流
    2. 拍照上传 - 按键或 HTTP 触发拍照，上传到远程服务器
    3. WiFi 配置 - 通过 Web 页面配置 WiFi 连接

启动方式 (Thonny):
    >>> import main_app
    >>> main_app.run()

硬件需求:
    - ESP32-S3-DevKitC-1 开发板
    - OV3660 摄像头模块 (通过排线连接)
    - 按键接 GPIO21 (可选，用于本地触发拍照)

依赖模块:
    - socket: TCP 网络通信
    - machine: 硬件控制 (GPIO、复位)
    - _thread: 多线程支持 (按键监听、拍照任务)
    - camera: 摄像头驱动 (camera.py)
    - wifimgr: WiFi 管理 (wifimgr.py)
"""

import socket
import machine
import time
import gc
import _thread
import json as json_mod
from wifimgr import WiFiManager
from camera import Camera

# ==================== 全局配置 ====================
BUTTON_PIN = 21     # 物理按键引脚 (GPIO21，上拉输入，按下接地)
SERVER_URL = "http://192.168.1.100:5000/upload"  # 远程服务器上传地址
IMAGE_TEXT = "ESP32-S3 CAM"  # 叠加在照片上的标识文字

# ==================== 全局状态 ====================
camera_obj = None       # 摄像头对象实例
wifi_manager = None     # WiFi 管理器实例
capture_flag = False    # 拍照触发标志 (True=需要拍照)
capture_lock = _thread.allocate_lock()  # 线程锁，保护 capture_flag 的并发访问


# ==================== Web 页面生成 ====================

def _build_main_html(ip, fps_info="~10"):
    """
    生成主控页面 HTML

    参数:
        ip (str): ESP32-S3 的 IP 地址
        fps_info (str): 当前帧率信息

    返回:
        str: 完整的 HTML 页面字符串
    """
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESP32-S3 CAM 实时图传</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#eee;min-height:100vh}}
.header{{background:#111;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.header h2{{font-size:18px}}
.controls{{display:flex;gap:8px;flex-wrap:wrap}}
.btn{{padding:8px 16px;border-radius:6px;border:none;font-size:13px;cursor:pointer;color:#fff}}
.btn-capture{{background:#e94560}}
.btn-capture:hover{{background:#c23152}}
.btn-capture:disabled{{background:#555;cursor:not-allowed}}
.btn-config{{background:#333}}
.info{{font-size:12px;color:#888;padding:8px 16px;background:#111;display:flex;justify-content:space-between;flex-wrap:wrap}}
.stream-container{{display:flex;justify-content:center;padding:8px}}
.stream-container img{{max-width:100%;height:auto;border-radius:4px}}
#status{{margin-top:4px;text-align:center;font-size:13px;color:#aaa;min-height:20px}}
</style>
</head>
<body>
<div class="header">
<h2>ESP32-S3 CAM</h2>
<div class="controls">
<button class="btn btn-capture" id="captureBtn" onclick="doCapture()">拍照上传</button>
<button class="btn btn-config" onclick="location.href='/config'">WiFi设置</button>
</div>
</div>
<div class="info">
<span>IP: {ip}</span>
<span>分辨率: 640x480 | FPS: {fps_info}</span>
</div>
<div class="stream-container">
<img id="stream" src="/stream" alt="MJPEG Stream">
</div>
<p id="status"></p>
<script>
async function doCapture(){{
var btn=document.getElementById('captureBtn');
var st=document.getElementById('status');
btn.disabled=true;st.textContent='拍照中...';
try{{
var res=await fetch('/capture');
var data=await res.json();
st.textContent=data.status==='ok'?'拍照上传成功':'失败: '+data.message;
}}catch(e){{st.textContent='请求失败: '+e.message}}
btn.disabled=false;
}}
</script>
</body>
</html>"""


def _build_config_html(wifi_mgr):
    """
    生成 WiFi 配置页面 HTML

    参数:
        wifi_mgr (WiFiManager): WiFi 管理器实例，用于扫描附近网络

    返回:
        str: 完整的 HTML 页面字符串
    """
    nets = wifi_mgr.scan_networks()
    options = ""
    for net in nets[:10]:  # 最多显示10个网络
        options += f'<option value="{net["ssid"]}">{net["ssid"]} ({net["rssi"]}dBm)</option>'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WiFi设置</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#1a1a2e;color:#eee;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}}
.card{{background:#16213e;border-radius:12px;padding:30px 25px;max-width:400px;width:100%}}
h2{{text-align:center;margin-bottom:20px}}
label{{display:block;margin-top:14px;margin-bottom:4px;font-size:14px;color:#aaa}}
input,select{{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #333;background:#0f3460;color:#eee;font-size:15px}}
.btn{{display:block;width:100%;margin-top:20px;padding:12px;background:#e94560;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}}
.back{{background:#333;margin-top:10px}}
#msg{{margin-top:14px;text-align:center;min-height:20px;font-size:13px}}
</style>
</head>
<body>
<div class="card">
<h2>WiFi 设置</h2>
<form id="form">
<label>WiFi名称</label>
<input type="text" id="ssid" list="netlist" placeholder="输入WiFi名">
<datalist id="netlist">{options}</datalist>
<label>密码</label>
<input type="password" id="password" placeholder="输入密码">
<button type="submit" class="btn">保存并重启</button>
</form>
<button class="btn back" onclick="location.href='/'">返回</button>
<p id="msg"></p>
</div>
<script>
document.getElementById('form').addEventListener('submit',async function(e){{
e.preventDefault();
var m=document.getElementById('msg');
m.textContent='保存中...';
try{{
var res=await fetch('/save_wifi',{{
method:'POST',body:JSON.stringify({{ssid:document.getElementById('ssid').value,password:document.getElementById('password').value}})
}});
var d=await res.json();
m.textContent=d.status==='ok'?'已保存，设备重启中...':'失败: '+d.message;
}}catch(e){{m.textContent='请求失败'}}
}});
</script>
</div>
</body>
</html>"""


# ==================== HTTP 服务器 ====================

def _send_response(client, status, content_type, body):
    """
    发送 HTTP 响应给客户端

    参数:
        client: socket 客户端连接对象
        status (str): HTTP 状态码文本 (如 "200 OK")
        content_type (str): 内容类型 (如 "text/html; charset=utf-8")
        body (str|bytes): 响应体内容
    """
    client.send(f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nConnection: close\r\n\r\n")
    if isinstance(body, str):
        client.send(body.encode("utf-8"))
    else:
        client.send(body)


def _stream_mjpeg(client):
    """
    向客户端推送 MJPEG 实时视频流

    使用 multipart/x-mixed-replace 协议，持续推送 JPEG 帧。
    客户端断开连接时自动停止。

    参数:
        client: socket 客户端连接对象
    """
    boundary = "FRAME_BOUNDARY"
    # 发送 MJPEG 流的 HTTP 头
    client.send(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: multipart/x-mixed-replace; boundary=" + boundary + "\r\n"
        "Cache-Control: no-cache\r\n"
        "Pragma: no-cache\r\n"
        "Connection: close\r\n\r\n"
    )
    while True:
        try:
            # 发送帧分隔符
            try:
                client.send("--" + boundary + "\r\n")
            except Exception:
                break  # 客户端断开

            # 捕获一帧图像
            frame = camera_obj.capture()
            if frame:
                # 发送帧头 (Content-Type + Content-Length)
                try:
                    client.send(f"Content-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n")
                except Exception:
                    break
                # 发送帧数据
                try:
                    client.sendall(frame)
                except Exception:
                    break
                # 发送帧尾
                try:
                    client.send("\r\n")
                except Exception:
                    break

            time.sleep(0.05)   # 控制帧间隔 (~20fps)
            gc.collect()       # 回收内存，防止 OOM
        except Exception:
            break

    try:
        client.close()
    except Exception:
        pass


def _handle_client(client):
    """
    处理单个 HTTP 客户端请求

    解析请求方法和路径，分发到对应的处理函数。
    支持的路由:
        GET  /           - 主控页面
        GET  /config     - WiFi 配置页面
        GET  /capture    - 触发拍照上传
        GET  /stream     - MJPEG 实时视频流
        GET  /wifi_status- WiFi 状态查询
        POST /save_wifi  - 保存 WiFi 配置并重启

    参数:
        client: socket 客户端连接对象
    """
    try:
        client.settimeout(2)
        req = client.recv(1024).decode("utf-8")
        if not req:
            client.close()
            return

        # 解析 HTTP 请求行: "GET /path HTTP/1.1"
        lines = req.split("\r\n")
        first_line = lines[0]
        parts = first_line.split(" ")
        if len(parts) < 2:
            client.close()
            return

        method = parts[0]
        path = parts[1]

        # MJPEG 视频流特殊处理 (长连接)
        if "/stream" in path:
            _stream_mjpeg(client)
            return

        # GET 请求路由
        if method == "GET":
            if path == "/" or path == "/index.html":
                _send_response(client, "200 OK", "text/html; charset=utf-8",
                               _build_main_html(wifi_manager.wlan.ifconfig()[0]))
            elif path == "/config":
                _send_response(client, "200 OK", "text/html; charset=utf-8",
                               _build_config_html(wifi_manager))
            elif path == "/capture":
                # 设置拍照标志，触发拍照任务线程执行
                global capture_flag
                with capture_lock:
                    capture_flag = True
                time.sleep(1)
                _send_response(client, "200 OK", "application/json",
                               '{"status":"ok","message":"已触发拍照上传"}')
            elif path == "/wifi_status":
                status = wifi_manager.get_status()
                _send_response(client, "200 OK", "application/json", json_mod.dumps(status))
            else:
                _send_response(client, "404 Not Found", "text/plain", "404")

        # POST 请求路由
        elif method == "POST":
            if path == "/save_wifi":
                # 从请求体中提取 JSON 数据
                body = ""
                for line in reversed(lines):
                    if line.strip():
                        body = line
                        break
                import json as j
                data = j.loads(body)
                # 保存 WiFi 配置到文件
                wifi_manager.save_config({
                    "ssid": data.get("ssid", ""),
                    "password": data.get("password", ""),
                    "static_ip": "", "subnet_mask": "", "gateway": ""
                })
                _send_response(client, "200 OK", "application/json", '{"status":"ok"}')
                time.sleep(0.5)
                machine.reset()  # 重启设备以应用新配置
            else:
                _send_response(client, "404 Not Found", "text/plain", "404")
        else:
            _send_response(client, "405 Method Not Allowed", "text/plain", "405")

        client.close()
    except Exception:
        try:
            client.close()
        except Exception:
            pass


# ==================== 图片上传 ====================

def _upload_to_server(buf):
    """
    将 JPEG 图片上传到远程服务器

    使用 multipart/form-data 格式上传，包含:
        - image: JPEG 图片文件
        - text:  标识文字

    参数:
        buf (bytes): JPEG 图像数据

    返回:
        bool: 上传成功返回 True，失败返回 False
    """
    try:
        import urequests
        boundary = "----ESP32Boundary"
        # 构建 multipart 请求体
        head = (
            "--" + boundary + "\r\n"
            "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
            "Content-Type: image/jpeg\r\n\r\n"
        )
        tail = (
            "\r\n--" + boundary + "\r\n"
            "Content-Disposition: form-data; name=\"text\"\r\n\r\n"
            + IMAGE_TEXT +
            "\r\n--" + boundary + "--\r\n"
        )
        body = head.encode() + buf + tail.encode()
        resp = urequests.post(
            SERVER_URL,
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
            timeout=10,
        )
        print(f"[上传] 响应: {resp.status_code} {resp.text}")
        resp.close()
        return True
    except Exception as e:
        print(f"[上传] 失败: {e}")
        return False


# ==================== 后台线程 ====================

def _button_thread():
    """
    按键监听线程 (独立线程运行)

    持续检测 GPIO21 上的按键状态，实现软件消抖。
    按下按键 (低电平) 时设置 capture_flag 触发拍照。

    注意: GPIO21 配置为上拉输入，按下按键接地产生低电平。
    """
    global capture_flag
    btn = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    last_state = 1      # 上次按键状态 (1=未按下)
    debounce = 0        # 消抖时间戳

    while True:
        state = btn.value()
        now = time.ticks_ms()
        # 状态变化时重置消抖计时
        if state != last_state:
            debounce = now
        # 消抖 300ms 后确认按键动作
        if time.ticks_diff(now, debounce) > 300:
            if state == 0 and last_state == 1:  # 下降沿: 未按下 -> 按下
                print("[按键] 触发拍照")
                with capture_lock:
                    capture_flag = True
        last_state = state
        time.sleep(0.05)  # 50ms 轮询间隔


def _capture_worker():
    """
    拍照任务线程 (独立线程运行)

    持续检查 capture_flag，为 True 时执行:
        1. 从摄像头捕获一帧图像
        2. 上传到远程服务器
        3. 清除标志
    """
    global capture_flag
    while True:
        need_capture = False
        # 原子操作: 读取并清除标志
        with capture_lock:
            if capture_flag:
                capture_flag = False
                need_capture = True

        if need_capture:
            print("[拍照] 开始拍照...")
            buf = camera_obj.capture()
            if buf:
                print(f"[拍照] 照片大小: {len(buf)} bytes")
                _upload_to_server(buf)
                print("[拍照] 完成")
            else:
                print("[拍照] 失败: 未获取到图像")

        time.sleep(0.1)  # 100ms 检查间隔


# ==================== 主入口 ====================

def run():
    """
    主程序入口

    执行流程:
        1. 初始化 WiFi 连接
        2. 初始化摄像头
        3. 启动按键监听和拍照任务线程
        4. 启动 HTTP 服务器 (端口 80)

    使用方法 (Thonny):
        >>> import main_app
        >>> main_app.run()
    """
    global camera_obj, wifi_manager

    # 1. 初始化 WiFi
    wifi_manager = WiFiManager()
    status = wifi_manager.get_status()
    if not status["connected"]:
        print("[错误] WiFi未连接，请先配置")
        return
    print(f"[主程序] WiFi已连接, IP: {status['ip']}")

    # 2. 初始化摄像头 (VGA 分辨率, 质量 12)
    camera_obj = Camera(framesize=Camera.FRAMESIZE_VGA, quality=12)
    camera_obj.init()

    # 3. 启动后台线程
    _thread.start_new_thread(_button_thread, ())    # 按键监听
    _thread.start_new_thread(_capture_worker, ())   # 拍照任务

    # 4. 启动 HTTP 服务器
    addr = ("0.0.0.0", 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    sock.listen(5)
    sock.settimeout(1)
    print(f"[HTTP] 服务器已启动 -> http://{status['ip']}")

    # 主循环: 接受客户端连接，分发给子线程处理
    while True:
        try:
            client, client_addr = sock.accept()
            _thread.start_new_thread(_handle_client, (client,))
        except OSError:
            pass  # 超时无连接，继续循环
