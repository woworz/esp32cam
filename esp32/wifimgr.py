import network
import time
import json
import uos
import machine
import gc


class WiFiManager:
    CONFIG_FILE = "/wifi_config.json"

    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

    def load_config(self):
        try:
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"ssid": "", "password": "", "static_ip": "", "subnet_mask": "", "gateway": ""}

    def save_config(self, config):
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def scan_networks(self):
        nets = self.wlan.scan()
        result = []
        for ssid, bssid, channel, rssi, authmode, hidden in nets:
            try:
                ssid_str = ssid.decode("utf-8")
            except Exception:
                ssid_str = str(ssid)
            result.append({"ssid": ssid_str, "rssi": rssi, "channel": channel})
        return sorted(result, key=lambda x: x["rssi"], reverse=True)

    def connect(self):
        config = self.load_config()
        ssid = config.get("ssid", "")
        password = config.get("password", "")

        if not ssid:
            print("[WiFi] 未配置WiFi，进入配置模式")
            return False

        self.wlan.connect(ssid, password)
        print(f"[WiFi] 正在连接 {ssid} ...")

        timeout = 15
        while timeout > 0:
            status = self.wlan.status()
            if status == network.STAT_GOT_IP:
                break
            if status == network.STAT_CONNECTING:
                time.sleep(0.5)
                timeout -= 0.5
                print(".", end="")
                continue
            if status in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND, network.STAT_CONNECT_FAIL):
                print(f"\n[WiFi] 连接失败 (status={status})")
                return False
            time.sleep(0.5)
            timeout -= 0.5
            print(".", end="")

        print()
        if self.wlan.status() != network.STAT_GOT_IP:
            print("[WiFi] 获取IP超时")
            return False

        ip, mask, gw, dns = self.wlan.ifconfig()
        print(f"[WiFi] 连接成功!")
        print(f"  IP:    {ip}")
        print(f"  掩码:  {mask}")
        print(f"  网关:  {gw}")
        return True

    def start_ap_mode(self):
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid="ESP32-CAM-Config", password="12345678", authmode=3)
        print("[WiFi] AP模式已启动: ESP32-CAM-Config / 12345678")
        print(f"  IP: {ap.ifconfig()[0]}")
        return ap

    def get_status(self):
        if self.wlan.isconnected():
            return {
                "connected": True,
                "ssid": self.wlan.config("essid"),
                "ip": self.wlan.ifconfig()[0],
            }
        return {"connected": False, "ssid": None, "ip": None}
