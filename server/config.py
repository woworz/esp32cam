"""
config.py - 服务端配置文件

本文件定义 Flask 服务端的所有可配置参数。
修改此文件可调整服务器行为，无需修改代码。

配置项说明:
    HOST            - 监听地址，"0.0.0.0" 表示接受所有网络接口的连接
    PORT            - 监听端口，默认 5000
    UPLOAD_FOLDER   - 原始上传图片保存目录
    PROCESSED_FOLDER- 处理后图片保存目录 (叠加文字/时间戳)
    FORWARD_URL     - 图片转发目标URL，None 表示不转发
    ESP32_URL       - ESP32 拍照触发地址，设置后可通过 /trigger 远程触发拍照
    FONT_PATH       - 自定义字体路径，None 使用系统默认字体
    TEXT_POSITION   - 文字叠加位置: "top" / "bottom" / "center"
    TEXT_COLOR      - 文字颜色 (R, G, B)
    TEXT_BG_COLOR   - 文字背景颜色 (R, G, B, A)，A=128 为半透明
"""

# ==================== 服务器基础配置 ====================
HOST = "0.0.0.0"           # 监听地址
PORT = 5000                # 监听端口

# ==================== 文件存储配置 ====================
UPLOAD_FOLDER = "uploads"          # 原始图片目录
PROCESSED_FOLDER = "processed"     # 处理后图片目录

# ==================== 转发配置 ====================
# 设置后，每次上传的图片会自动转发到此 URL
# 格式: "http://目标服务器:端口/路径"
FORWARD_URL = None

# ==================== ESP32 远程控制配置 ====================
# 设置为 ESP32 的 /capture 地址，可通过服务端 /trigger 接口远程触发拍照
# 格式: "http://ESP32_IP/capture"
ESP32_URL = None

# ==================== 图片处理配置 ====================
# 自定义字体路径 (TrueType)，None 使用系统默认字体
# Windows 示例: "C:/Windows/Fonts/simhei.ttf"
# Linux 示例: "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
FONT_PATH = None

# 文字叠加位置: "top" (顶部) / "bottom" (底部) / "center" (居中)
TEXT_POSITION = "bottom"

# 文字颜色 (R, G, B)，白色
TEXT_COLOR = (255, 255, 255)

# 文字背景颜色 (R, G, B, A)，半透明黑色
TEXT_BG_COLOR = (0, 0, 0, 128)

# ==================== CORS 配置 ====================
# 允许跨域请求的源，["*"] 表示允许所有来源
CORS_ORIGINS = ["*"]
