import machine
import time
import gc
from wifimgr import WiFiManager


def main():
    print("\n" + "=" * 40)
    print("  ESP32-CAM MicroPython 图传设备")
    print("=" * 40)

    gc.collect()
    print(f"[启动] 可用内存: {gc.mem_free()} bytes")

    wifi = WiFiManager()

    if not wifi.connect():
        print("[启动] WiFi连接失败，启动AP配置模式...")
        ap = wifi.start_ap_mode()
    else:
        ap = None

    if ap:
        import wificonfig_server
        wificonfig_server.run(wifi, ap)
        machine.reset()

    print("[启动] 进入主程序...")
    time.sleep(1)

    try:
        import main_app
        main_app.run()
    except KeyboardInterrupt:
        print("\n[退出] 程序已终止")
    except Exception as e:
        print(f"[错误] {e}")
        import sys
        try:
            sys.print_exception(e)
        except Exception:
            pass
        print("[重启] 5秒后重启...")
        time.sleep(5)
        machine.reset()


if __name__ == "__main__":
    main()
