"""
ESP32-S3 CAM 主程序。

设备只作为公网服务器的客户端运行：
1. 轮询服务器命令队列；
2. 收到 capture 命令或本地按键触发后拍照；
3. 将 JPEG 上传到公网服务器；
4. 回报远程命令执行结果。

日常运行不再启动板载 HTTP/MJPEG 服务器。首次配网所需的临时 AP
配置服务仍由 boot.py 和 wificonfig_server.py 负责。
"""

import gc
import json
import machine
import time

from ovcam import Camera
from tft_display import ST7789
from wifimgr import WiFiManager


BUTTON_PIN = 21
DEVICE_ID = "esp32-s3-cam"
SERVER_BASE_URL = "http://154.21.201.13"
UPLOAD_URL = SERVER_BASE_URL + "/upload"
COMMAND_URL = (
    SERVER_BASE_URL
    + "/api/device/commands/next?device_id="
    + DEVICE_ID
)
COMMAND_RESULT_BASE_URL = SERVER_BASE_URL + "/api/device/commands/"
COMMAND_POLL_INTERVAL_MS = 2000
IMAGE_TEXT = "ESP32-S3 CAM"

camera_obj = None
tft_obj = None
wifi_manager = None


def _close_response(response):
    if response:
        try:
            response.close()
        except Exception:
            pass


def _upload_to_server(image_data):
    """使用 multipart/form-data 将 JPEG 上传到公网服务器。"""
    response = None
    try:
        import urequests

        boundary = "----ESP32Boundary"
        head = (
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="image"; '
            'filename="capture.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        )
        tail = (
            "\r\n--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="text"\r\n\r\n'
            + IMAGE_TEXT
            + "\r\n--"
            + boundary
            + "\r\n"
            'Content-Disposition: form-data; name="device_id"\r\n\r\n'
            + DEVICE_ID
            + "\r\n--"
            + boundary
            + "--\r\n"
        )
        body = head.encode() + image_data + tail.encode()
        response = urequests.post(
            UPLOAD_URL,
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
            timeout=20,
        )
        success = 200 <= response.status_code < 300
        print("[上传] HTTP {}，结果: {}".format(response.status_code, success))
        return success
    except Exception as exc:
        print("[上传] 失败: {}".format(exc))
        return False
    finally:
        _close_response(response)
        gc.collect()


def _poll_remote_command():
    """轮询服务器并领取一条待执行命令。"""
    response = None
    try:
        import urequests

        response = urequests.get(COMMAND_URL, timeout=10)
        if response.status_code != 200:
            print("[命令] 轮询 HTTP {}".format(response.status_code))
            return None
        payload = response.json()
        return payload.get("command")
    except Exception as exc:
        print("[命令] 轮询失败: {}".format(exc))
        return None
    finally:
        _close_response(response)
        gc.collect()


def _report_command_result(command_id, status, message=""):
    """向服务器回报命令执行结果。"""
    response = None
    try:
        import urequests

        url = COMMAND_RESULT_BASE_URL + command_id + "/result"
        body = json.dumps(
            {
                "device_id": DEVICE_ID,
                "status": status,
                "message": message,
            }
        )
        response = urequests.post(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        success = 200 <= response.status_code < 300
        print("[命令] 回报 HTTP {}，结果: {}".format(response.status_code, success))
        return success
    except Exception as exc:
        print("[命令] 回报失败: {}".format(exc))
        return False
    finally:
        _close_response(response)
        gc.collect()


def _display_on_tft(image_data):
    """在 TFT 上显示本次拍照结果或状态提示。"""
    if not tft_obj:
        return

    try:
        import jpegdecoder

        decoder = jpegdecoder.JPEGDecoder()
        decoder.decode(image_data)
        rgb_data = decoder.get_rgb_data()
        tft_obj.show_image(rgb_data, 0, 0, decoder.width, decoder.height)
    except ImportError:
        tft_obj.fill(0x0000)
        tft_obj.show_text("Photo Captured", 40, 150, 0x07E0, 1)
        tft_obj.show_text(
            "Size: {}B".format(len(image_data)), 60, 180, 0xFFFF, 1
        )
    except Exception as exc:
        print("[TFT] 显示失败: {}".format(exc))
        tft_obj.fill(0x0000)
        tft_obj.show_text("Display Error", 50, 150, 0xF800, 1)


def _capture_and_upload():
    """完成一次拍照、显示和上传，返回是否成功。"""
    print("[拍照] 开始")
    try:
        image_data = camera_obj.capture()
        if not image_data:
            print("[拍照] 未获取到图像")
            return False
        print("[拍照] 大小: {} bytes".format(len(image_data)))
        _display_on_tft(image_data)
        return _upload_to_server(image_data)
    except Exception as exc:
        print("[拍照] 异常: {}".format(exc))
        return False
    finally:
        gc.collect()


def _ensure_wifi():
    """WiFi 断线时尝试重新连接。"""
    if wifi_manager.get_status()["connected"]:
        return True
    print("[WiFi] 连接已断开，正在重连")
    return wifi_manager.connect()


def run():
    """初始化硬件并进入按键检测与远程命令轮询主循环。"""
    global camera_obj, tft_obj, wifi_manager

    wifi_manager = WiFiManager()
    status = wifi_manager.get_status()
    if not status["connected"]:
        print("[错误] WiFi 未连接，请重启设备进入配网流程")
        return
    print("[主程序] WiFi 已连接，IP: {}".format(status["ip"]))

    camera_obj = Camera(framesize=Camera.FRAMESIZE_VGA, quality=12)
    camera_obj.init()

    tft_obj = ST7789()
    tft_obj.init()
    tft_obj.fill(0x001F)
    tft_obj.show_text("ESP32-CAM", 80, 140, 0x07E0, 2)
    tft_obj.show_text("Cloud Ready", 90, 175, 0xFFFF, 1)

    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    last_button_state = button.value()
    last_button_time = time.ticks_ms()
    next_command_poll = time.ticks_add(
        time.ticks_ms(), COMMAND_POLL_INTERVAL_MS
    )

    print("[主程序] 云端轮询已启动，设备 ID: {}".format(DEVICE_ID))

    try:
        while True:
            now = time.ticks_ms()
            button_state = button.value()

            if (
                button_state == 0
                and last_button_state == 1
                and time.ticks_diff(now, last_button_time) > 300
            ):
                last_button_time = now
                print("[按键] 本地触发拍照")
                _capture_and_upload()
            last_button_state = button_state

            if time.ticks_diff(now, next_command_poll) >= 0:
                next_command_poll = time.ticks_add(
                    now, COMMAND_POLL_INTERVAL_MS
                )
                if _ensure_wifi():
                    command = _poll_remote_command()
                    if command and command.get("type") == "capture":
                        command_id = command.get("id")
                        print("[命令] 执行 capture: {}".format(command_id))
                        success = _capture_and_upload()
                        _report_command_result(
                            command_id,
                            "completed" if success else "failed",
                            "图片上传成功" if success else "拍照或上传失败",
                        )

            time.sleep(0.05)
    finally:
        if camera_obj:
            camera_obj.deinit()
        if tft_obj:
            tft_obj.deinit()
