"""
wificonfig_server.py - WiFi 配置服务器 (AP 模式专用)

本模块在 AP 模式下运行，提供一个 Web 页面让用户配置 WiFi 连接。
当 ESP32-S3 无法连接到已保存的 WiFi 时，可启动此模块进行配置。

工作流程:
    1. ESP32-S3 启动 AP 热点 "ESP32-CAM-Config"
    2. 用户手机/电脑连接此热点
    3. 浏览器访问 http://192.168.4.1
    4. 在页面上选择/输入 WiFi 名称和密码
    5. 保存后 ESP32-S3 重启，尝试连接新配置的 WiFi

依赖: socket, json, network, wifimgr
"""

import socket
import json
import network


def _build_html(wifi_manager):
    """
    生成 WiFi 配置页面 HTML

    扫描附近的 WiFi 网络，生成包含下拉列表的配置表单。

    参数:
        wifi_manager (WiFiManager): WiFi 管理器实例

    返回:
        str: 完整的 HTML 页面字符串
    """
    nets = wifi_manager.scan_networks()
    options = ""
    for net in nets:
        options += f'<option value="{net["ssid"]}">{net["ssid"]} ({net["rssi"]}dBm)</option>'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESP32-CAM WiFi配置</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#1a1a2e;color:#eee;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}}
.card{{background:#16213e;border-radius:12px;padding:30px 25px;max-width:400px;width:100%}}
h2{{text-align:center;margin-bottom:6px}}
.sub{{color:#888;font-size:13px;text-align:center;margin-bottom:20px}}
label{{display:block;margin-top:14px;margin-bottom:4px;font-size:14px;color:#aaa}}
input,select{{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #333;background:#0f3460;color:#eee;font-size:15px}}
input:focus,select:focus{{outline:none;border-color:#e94560}}
.btn{{display:block;width:100%;margin-top:20px;padding:12px;background:#e94560;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}}
.btn:hover{{background:#c23152}}
#msg{{margin-top:14px;text-align:center;font-size:13px;min-height:20px}}
</style>
</head>
<body>
<div class="card">
<h2>WiFi 配置</h2>
<p class="sub">请选择或输入WiFi名称和密码</p>
<form id="wifiForm">
<label>WiFi 名称</label>
<input type="text" id="ssid" list="networkList" placeholder="输入WiFi名称">
<datalist id="networkList">{options}</datalist>
<label>WiFi 密码</label>
<input type="password" id="password" placeholder="输入WiFi密码">
<button type="submit" class="btn">保存并连接</button>
</form>
<p id="msg"></p>
</div>
<script>
document.getElementById('wifiForm').addEventListener('submit',async function(e){{
e.preventDefault();
var msg=document.getElementById('msg');
msg.style.color='#aaa';
msg.textContent='正在连接...';
try{{
var res=await fetch('/save',{{
method:'POST',
headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{
ssid:document.getElementById('ssid').value,
password:document.getElementById('password').value
}})
}});
var data=await res.json();
if(data.status==='ok'){{
msg.style.color='#4ecca3';
msg.textContent='连接成功! 设备将重启...';
}}else{{
msg.style.color='#e94560';
msg.textContent='失败: '+data.message;
}}
}}catch(e){{
msg.style.color='#e94560';
msg.textContent='请求失败: '+e.message;
}}
}});
</script>
</body>
</html>"""


def _handle_http(client, wifi_manager):
    """
    处理 HTTP 请求

    参数:
        client: socket 客户端连接
        wifi_manager (WiFiManager): WiFi 管理器实例

    返回:
        bool: True 继续服务, False 保存配置后关闭 (设备将重启)
    """
    try:
        client.settimeout(5)
        req = client.recv(1024).decode("utf-8")
        if not req:
            client.close()
            return True

        # 解析请求行
        lines = req.split("\r\n")
        first = lines[0]
        method, path, _ = first.split(" ")

        # GET / - 显示配置页面
        if method == "GET" and (path == "/" or path == "/index.html"):
            html = _build_html(wifi_manager)
            resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n" + html
            client.send(resp.encode("utf-8"))

        # POST /save - 保存 WiFi 配置
        elif method == "POST" and path == "/save":
            body = lines[-1] if lines[-1] else ""
            data = json.loads(body)
            ssid = data.get("ssid", "")
            password = data.get("password", "")
            # 保存配置到文件
            wifi_manager.save_config({"ssid": ssid, "password": password, "static_ip": "", "subnet_mask": "", "gateway": ""})
            # 返回成功响应
            resp = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{"status":"ok"}'
            client.send(resp.encode("utf-8"))
            client.close()
            # 延迟后重启设备，使新配置生效
            import machine
            import time
            time.sleep(1)
            machine.reset()
            return False

        # 其他路径返回 404
        else:
            resp = "HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"
            client.send(resp.encode("utf-8"))

        client.close()
        return True
    except Exception:
        try:
            client.close()
        except Exception:
            pass
        return True


def run(wifi_manager, ap):
    """
    启动 WiFi 配置服务器

    在 AP 模式下运行，监听 80 端口，提供 Web 配置界面。

    参数:
        wifi_manager (WiFiManager): WiFi 管理器实例
        ap: AP 模式接口对象 (由 WiFiManager.start_ap_mode() 返回)

    使用方式:
        wm = WiFiManager()
        ap = wm.start_ap_mode()
        wificonfig_server.run(wm, ap)
    """
    addr = ("0.0.0.0", 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    sock.listen(5)
    sock.settimeout(2)
    print("[Config] 配置服务器已启动 -> http://192.168.4.1")

    while True:
        try:
            client, client_addr = sock.accept()
            if not _handle_http(client, wifi_manager):
                sock.close()
                return  # 用户保存配置后关闭服务器，设备将重启
        except OSError:
            pass  # 超时无连接，继续循环
