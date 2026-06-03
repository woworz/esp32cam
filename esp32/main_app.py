import socket
import machine
import time
import gc
import _thread
import json as json_mod
from wifimgr import WiFiManager
from camera import Camera


BUTTON_PIN = 21   # GPIO4已被摄像头SIOD占用，改用GPIO21
SERVER_URL = "http://192.168.1.100:5000/upload"
IMAGE_TEXT = "ESP32-S3 CAM"

camera_obj = None
wifi_manager = None
capture_flag = False
capture_lock = _thread.allocate_lock()


def _build_main_html(ip, fps_info="~10"):
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
    nets = wifi_mgr.scan_networks()
    options = ""
    for net in nets[:10]:
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


def _send_response(client, status, content_type, body):
    client.send(f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nConnection: close\r\n\r\n")
    if isinstance(body, str):
        client.send(body.encode("utf-8"))
    else:
        client.send(body)


def _stream_mjpeg(client):
    boundary = "FRAME_BOUNDARY"
    client.send(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: multipart/x-mixed-replace; boundary=" + boundary + "\r\n"
        "Cache-Control: no-cache\r\n"
        "Pragma: no-cache\r\n"
        "Connection: close\r\n\r\n"
    )
    while True:
        try:
            try:
                client.send("--" + boundary + "\r\n")
            except Exception:
                break

            frame = camera_obj.capture()
            if frame:
                try:
                    client.send(f"Content-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n")
                except Exception:
                    break
                try:
                    client.sendall(frame)
                except Exception:
                    break
                try:
                    client.send("\r\n")
                except Exception:
                    break

            time.sleep(0.05)
            gc.collect()
        except Exception:
            break

    try:
        client.close()
    except Exception:
        pass


def _handle_client(client):
    try:
        client.settimeout(2)
        req = client.recv(1024).decode("utf-8")
        if not req:
            client.close()
            return

        lines = req.split("\r\n")
        first_line = lines[0]
        parts = first_line.split(" ")
        if len(parts) < 2:
            client.close()
            return

        method = parts[0]
        path = parts[1]

        if "/stream" in path:
            _stream_mjpeg(client)
            return

        if method == "GET":
            if path == "/" or path == "/index.html":
                _send_response(client, "200 OK", "text/html; charset=utf-8",
                               _build_main_html(wifi_manager.wlan.ifconfig()[0]))
            elif path == "/config":
                _send_response(client, "200 OK", "text/html; charset=utf-8",
                               _build_config_html(wifi_manager))
            elif path == "/capture":
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
        elif method == "POST":
            if path == "/save_wifi":
                body = ""
                for line in reversed(lines):
                    if line.strip():
                        body = line
                        break
                import json as j
                data = j.loads(body)
                wifi_manager.save_config({
                    "ssid": data.get("ssid", ""),
                    "password": data.get("password", ""),
                    "static_ip": "", "subnet_mask": "", "gateway": ""
                })
                _send_response(client, "200 OK", "application/json", '{"status":"ok"}')
                time.sleep(0.5)
                machine.reset()
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


def _upload_to_server(buf):
    try:
        import urequests
        boundary = "----ESP32Boundary"
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


def _button_thread():
    global capture_flag
    btn = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    last_state = 1
    debounce = 0

    while True:
        state = btn.value()
        now = time.ticks_ms()
        if state != last_state:
            debounce = now
        if time.ticks_diff(now, debounce) > 300:
            if state == 0 and last_state == 1:
                print("[按键] 触发拍照")
                with capture_lock:
                    capture_flag = True
        last_state = state
        time.sleep(0.05)


def _capture_worker():
    global capture_flag
    while True:
        need_capture = False
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

        time.sleep(0.1)


def run():
    global camera_obj, wifi_manager

    wifi_manager = WiFiManager()
    status = wifi_manager.get_status()
    if not status["connected"]:
        print("[错误] WiFi未连接，请先配置")
        return
    print(f"[主程序] WiFi已连接, IP: {status['ip']}")

    camera_obj = Camera(framesize=Camera.FRAMESIZE_VGA, quality=12)
    camera_obj.init()

    _thread.start_new_thread(_button_thread, ())
    _thread.start_new_thread(_capture_worker, ())

    addr = ("0.0.0.0", 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    sock.listen(5)
    sock.settimeout(1)
    print(f"[HTTP] 服务器已启动 -> http://{status['ip']}")

    while True:
        try:
            client, client_addr = sock.accept()
            _thread.start_new_thread(_handle_client, (client,))
        except OSError:
            pass
