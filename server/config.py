"""
config.py - 服务端配置文件

本文件定义 Flask 服务端的所有可配置参数。
修改此文件可调整服务器行为，无需修改代码。

配置项说明:
    HOST            - 监听地址，"0.0.0.0" 表示接受所有网络接口的连接
    PORT            - 监听端口，默认 5000
    UPLOAD_FOLDER   - 原始上传图片保存目录
    PROCESSED_FOLDER- 处理后图片保存目录 (叠加文字/时间戳)
    COMMAND_STATE_FILE - 远程命令与设备心跳状态文件
    FONT_PATH       - 自定义字体路径，None 使用系统默认字体
    TEXT_POSITION   - 文字叠加位置: "top" / "bottom" / "center"
    TEXT_COLOR      - 文字颜色 (R, G, B)
    TEXT_BG_COLOR   - 文字背景颜色 (R, G, B, A)，A=128 为半透明
"""

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 服务器基础配置 ====================
HOST = os.getenv("ESP_CAM_HOST", "0.0.0.0")
PORT = int(os.getenv("ESP_CAM_PORT", "5000"))

# ==================== 文件存储配置 ====================
UPLOAD_FOLDER = os.path.abspath(
    os.getenv("ESP_CAM_UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
)
PROCESSED_FOLDER = os.path.abspath(
    os.getenv("ESP_CAM_PROCESSED_FOLDER", os.path.join(BASE_DIR, "processed"))
)

# ==================== 设备命令配置 ====================
COMMAND_STATE_FILE = os.path.abspath(
    os.getenv(
        "ESP_CAM_COMMAND_STATE_FILE",
        os.path.join(BASE_DIR, "commands.json"),
    )
)
DEFAULT_DEVICE_ID = os.getenv("ESP_CAM_DEFAULT_DEVICE_ID", "esp32-s3-cam")
DEVICE_ONLINE_TIMEOUT = int(
    os.getenv("ESP_CAM_DEVICE_ONLINE_TIMEOUT", "15")
)
COMMAND_CLAIM_TIMEOUT = int(
    os.getenv("ESP_CAM_COMMAND_CLAIM_TIMEOUT", "60")
)

# ==================== 图片处理配置 ====================
# 自定义字体路径 (TrueType)，None 使用系统默认字体
# Windows 示例: "C:/Windows/Fonts/simhei.ttf"
# Linux 示例: "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
FONT_PATH = os.getenv("ESP_CAM_FONT_PATH") or None

# 文字叠加位置: "top" (顶部) / "bottom" (底部) / "center" (居中)
TEXT_POSITION = "bottom"

# 文字颜色 (R, G, B)，白色
TEXT_COLOR = (255, 255, 255)

# 文字背景颜色 (R, G, B, A)，半透明黑色
TEXT_BG_COLOR = (0, 0, 0, 128)
