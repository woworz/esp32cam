import socket
import json
import network


def _build_html(wifi_manager):
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
    try:
        client.settimeout(5)
        req = client.recv(1024).decode("utf-8")
        if not req:
            client.close()
            return True

        lines = req.split("\r\n")
        first = lines[0]
        method, path, _ = first.split(" ")

        if method == "GET" and (path == "/" or path == "/index.html"):
            html = _build_html(wifi_manager)
            resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n" + html
            client.send(resp.encode("utf-8"))
        elif method == "POST" and path == "/save":
            body = lines[-1] if lines[-1] else ""
            data = json.loads(body)
            ssid = data.get("ssid", "")
            password = data.get("password", "")
            wifi_manager.save_config({"ssid": ssid, "password": password, "static_ip": "", "subnet_mask": "", "gateway": ""})
            resp = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{"status":"ok"}'
            client.send(resp.encode("utf-8"))
            client.close()
            import machine
            import time
            time.sleep(1)
            machine.reset()
            return False
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
                return
        except OSError:
            pass
