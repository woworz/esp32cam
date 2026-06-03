"""
wifimgr.py - WiFi 管理模块

本模块负责 ESP32-S3 的 WiFi 连接管理，包括:
    1. 从文件加载/保存 WiFi 配置
    2. 扫描附近的 WiFi 网络
    3. 连接到指定的 WiFi 网络
    4. 启动 AP 模式供用户配置
    5. 查询当前连接状态

WiFi 配置存储在 /wifi_config.json 文件中，格式:
    {
        "ssid": "WiFi名称",
        "password": "WiFi密码",
        "static_ip": "",
        "subnet_mask": "",
        "gateway": ""
    }

依赖: MicroPython network 模块
"""

import network
import time
import json
import uos
import machine
import gc


class WiFiManager:
    """
    WiFi 连接管理器

    提供 STA (客户端) 和 AP (热点) 两种模式的管理功能。
    首次使用时需要通过 AP 模式或手动编辑配置文件来设置 WiFi。

    使用示例:
        wm = WiFiManager()
        if wm.connect():
            print("WiFi 已连接")
        else:
            ap = wm.start_ap_mode()
            # 启动配置服务器...
    """

    # WiFi 配置文件路径 (ESP32-S3 内部文件系统)
    CONFIG_FILE = "/wifi_config.json"

    def __init__(self):
        """初始化 WiFi 管理器，激活 STA 模式"""
        self.wlan = network.WLAN(network.STA_IF)  # 创建 STA 接口
        self.wlan.active(True)                     # 激活接口

    def load_config(self):
        """
        从文件加载 WiFi 配置

        返回:
            dict: 包含 ssid, password, static_ip, subnet_mask, gateway 的字典
                  文件不存在或读取失败时返回空配置
        """
        try:
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            # 文件不存在或格式错误，返回空配置
            return {"ssid": "", "password": "", "static_ip": "", "subnet_mask": "", "gateway": ""}

    def save_config(self, config):
        """
        保存 WiFi 配置到文件

        参数:
            config (dict): WiFi 配置字典
        """
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print(f"[WiFi] 配置已保存到 {self.CONFIG_FILE}")

    def scan_networks(self):
        """
        扫描附近的 WiFi 网络

        返回:
            list: 按信号强度降序排列的网络列表
                  每个元素为 dict: {"ssid": str, "rssi": int, "channel": int}
        """
        nets = self.wlan.scan()
        result = []
        for ssid, bssid, channel, rssi, authmode, hidden in nets:
            try:
                ssid_str = ssid.decode("utf-8")
            except Exception:
                ssid_str = str(ssid)
            result.append({"ssid": ssid_str, "rssi": rssi, "channel": channel})
        # 按信号强度降序排列
        return sorted(result, key=lambda x: x["rssi"], reverse=True)

    def connect(self):
        """
        连接到配置的 WiFi 网络

        从配置文件读取 SSID 和密码，尝试连接。
        超时时间 15 秒。

        返回:
            bool: 连接成功返回 True，失败返回 False
        """
        config = self.load_config()
        ssid = config.get("ssid", "")
        password = config.get("password", "")

        if not ssid:
            print("[WiFi] 未配置WiFi，进入配置模式")
            return False

        self.wlan.connect(ssid, password)
        print(f"[WiFi] 正在连接 {ssid} ...")

        # 等待连接，最多 15 秒
        timeout = 15
        while timeout > 0:
            status = self.wlan.status()
            if status == network.STAT_GOT_IP:
                break  # 获取到 IP，连接成功
            if status == network.STAT_CONNECTING:
                time.sleep(0.5)
                timeout -= 0.5
                print(".", end="")
                continue
            # 连接失败 (密码错误、找不到AP等)
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

        # 连接成功，打印网络信息
        ip, mask, gw, dns = self.wlan.ifconfig()
        print(f"[WiFi] 连接成功!")
        print(f"  IP:    {ip}")
        print(f"  掩码:  {mask}")
        print(f"  网关:  {gw}")
        return True

    def start_ap_mode(self):
        """
        启动 AP (热点) 模式

        创建名为 "ESP32-CAM-Config" 的热点，密码 "12345678"。
        用户连接此热点后可通过 192.168.4.1 访问配置页面。

        返回:
            network.WLAN: AP 接口对象
        """
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid="ESP32-CAM-Config", password="12345678", authmode=3)
        print("[WiFi] AP模式已启动: ESP32-CAM-Config / 12345678")
        print(f"  IP: {ap.ifconfig()[0]}")
        return ap

    def get_status(self):
        """
        获取当前 WiFi 连接状态

        返回:
            dict: 连接状态字典
                - connected (bool): 是否已连接
                - ssid (str): 连接的 WiFi 名称 (未连接时为 None)
                - ip (str): 分配的 IP 地址 (未连接时为 None)
        """
        if self.wlan.isconnected():
            return {
                "connected": True,
                "ssid": self.wlan.config("essid"),
                "ip": self.wlan.ifconfig()[0],
            }
        return {"connected": False, "ssid": None, "ip": None}
