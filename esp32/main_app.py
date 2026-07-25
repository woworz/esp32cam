"""
main_app.py - ESP32-S3 CAM 主程序

本模块是 ESP32-S3 的核心运行程序，提供以下功能:
    1. HTTP 服务器 - 提供 Web 控制界面和 MJPEG 实时视频流
    2. 拍照上传 - 按键或 HTTP 触发拍照，上传到远程服务器
    3. WiFi 配置 - AP 模式配网 (wificonfig_server.py)

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
    - ovcam: 摄像头驱动 (ovcam.py)
    - wifimgr: WiFi 管理 (wifimgr.py)
"""

import socket
import machine
import time
import gc
import _thread
import json as json_mod
from wifimgr import WiFiManager
from ovcam import Camera
from tft_display import ST7789

# ==================== 全局配置 ====================
BUTTON_PIN = 21     # 物理按键引脚 (GPIO21，上拉输入，按下接地)
SERVER_URL = "http://192.168.1.100:5000/upload"  # 远程服务器上传地址
IMAGE_TEXT = "ESP32-S3 CAM"  # 叠加在照片上的标识文字

# ==================== 全局状态 ====================
camera_obj = None       # 摄像头对象实例
tft_obj = None          # TFT 显示屏对象实例
wifi_manager = None     # WiFi 管理器实例
capture_flag = False    # 拍照触发标志 (True=需要拍照)
capture_lock = _thread.allocate_lock()  # 线程锁，保护 capture_flag 的并发访问
camera_lock = _thread.allocate_lock()   # 避免视频流和拍照任务并发访问摄像头


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
    client.send("HTTP/1.1 {}\r\nContent-Type: {}\r\nConnection: close\r\n\r\n".format(status, content_type))
    if isinstance(body, str):
        client.send(body.encode("utf-8"))
    else:
        client.send(body)


def _send_file(client, path, content_type):
    """从板载文件系统分块发送静态文件。"""
    try:
        file_obj = open(path, "rb")
    except OSError:
        _send_response(client, "500 Internal Server Error", "text/plain",
                       "Missing board file: " + path)
        return

    try:
        client.send(
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: {}\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n\r\n".format(content_type)
        )
        while True:
            chunk = file_obj.read(1024)
            if not chunk:
                break
            client.sendall(chunk)
    finally:
        file_obj.close()


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
            with camera_lock:
                frame = camera_obj.capture()
            if frame:
                # 发送帧头 (Content-Type + Content-Length)
                try:
                    client.send("Content-Type: image/jpeg\r\nContent-Length: {}\r\n\r\n".format(len(frame)))
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
                _send_file(client, "index.html", "text/html; charset=utf-8")
            elif path == "/config":
                _send_response(client, "200 OK", "application/json",
                               '{"status":"ok","message":"WiFi config via AP mode"}')
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
        print("[上传] 响应: {} {}".format(resp.status_code, resp.text))
        resp.close()
        return True
    except Exception as e:
        print("[上传] 失败: {}".format(e))
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


def _display_on_tft(img_data):
    """
    将 JPEG 图像显示在 TFT 屏幕上

    参数:
        img_data (bytes): JPEG 格式的图像数据

    注意: 需要 JPEG 解码库支持。如果没有解码库，会显示提示信息。
    """
    if not tft_obj:
        return

    try:
        # 尝试使用 JPEG 解码库 (如果可用)
        import jpegdecoder
        decoder = jpegdecoder.JPEGDecoder()
        decoder.decode(img_data)
        rgb_data = decoder.get_rgb_data()
        tft_obj.show_image(rgb_data, 0, 0, decoder.width, decoder.height)
    except ImportError:
        # 没有 JPEG 解码库，显示提示信息
        tft_obj.fill(0x0000)
        tft_obj.show_text("Photo Captured", 40, 150, 0x07E0, 1)
        tft_obj.show_text("Size: {}B".format(len(img_data)), 60, 180, 0xFFFF, 1)
    except Exception as e:
        print("[TFT] 显示失败: {}".format(e))
        tft_obj.fill(0x0000)
        tft_obj.show_text("Display Error", 50, 150, 0xF800, 1)


def _capture_worker():
    """
    拍照任务线程 (独立线程运行)

    持续检查 capture_flag，为 True 时执行:
        1. 从摄像头捕获一帧图像
        2. 显示在 TFT 屏幕上
        3. 上传到远程服务器
        4. 清除标志
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
            with camera_lock:
                buf = camera_obj.capture()
            if buf:
                print("[拍照] 照片大小: {} bytes".format(len(buf)))
                # 显示在 TFT 屏幕上
                _display_on_tft(buf)
                # 上传到服务器
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
        3. 初始化 TFT 显示屏
        4. 启动按键监听和拍照任务线程
        5. 启动 HTTP 服务器 (端口 80)

    使用方法 (Thonny):
        >>> import main_app
        >>> main_app.run()
    """
    global camera_obj, tft_obj, wifi_manager

    # 1. 初始化 WiFi
    wifi_manager = WiFiManager()
    status = wifi_manager.get_status()
    if not status["connected"]:
        print("[错误] WiFi未连接，请先配置")
        return
    print("[主程序] WiFi已连接, IP: {}".format(status['ip']))

    # 2. 初始化摄像头 (VGA 分辨率, 质量 12)
    camera_obj = Camera(framesize=Camera.FRAMESIZE_VGA, quality=12)
    camera_obj.init()

    # 3. 初始化 TFT 显示屏
    tft_obj = ST7789()
    tft_obj.init()
    tft_obj.fill(0x001F)  # 蓝色测试背景，便于确认屏幕通信正常
    tft_obj.show_text("ESP32-CAM", 80, 150, 0x07E0, 2)  # 绿色文字

    # 4. 启动后台线程
    _thread.start_new_thread(_button_thread, ())    # 按键监听
    _thread.start_new_thread(_capture_worker, ())   # 拍照任务

    # 5. 启动 HTTP 服务器
    addr = ("0.0.0.0", 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    sock.listen(5)
    sock.settimeout(1)
    print("[HTTP] 服务器已启动 -> http://{}".format(status['ip']))

    # 主循环: 接受客户端连接，分发给子线程处理
    while True:
        try:
            client, client_addr = sock.accept()
            _thread.start_new_thread(_handle_client, (client,))
        except OSError:
            pass  # 超时无连接，继续循环
