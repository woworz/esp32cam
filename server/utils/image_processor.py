"""
image_processor.py - 图片处理工具模块

本模块提供图片叠加文字/时间戳的功能。
使用 Pillow (PIL) 库进行图像处理。

功能:
    1. add_text_overlay()  - 在图片上叠加文字 (带半透明背景)
    2. build_timestamp_text() - 构建带时间戳的文字

依赖:
    - Pillow: pip install Pillow
    - 字体: 优先使用 SimHei (黑体)，其次 Arial，最后使用默认字体
"""

import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


def add_text_overlay(
    image_path: str,
    text: str,
    output_path: str,
    position: str = "bottom",
    text_color: tuple = (255, 255, 255),
    bg_color: tuple = (0, 0, 0, 128),
    font_path: str = None,
) -> str:
    """
    在图片上叠加文字 (带半透明背景)

    处理流程:
        1. 打开原始图片并转换为 RGBA 模式
        2. 创建透明叠加层
        3. 绘制半透明背景矩形
        4. 绘制文字
        5. 合并叠加层到原图
        6. 转换为 RGB 并保存为 JPEG

    参数:
        image_path (str): 原始图片路径
        text (str): 要叠加的文字内容
        output_path (str): 输出图片路径
        position (str): 文字位置
            - "top":    顶部居中
            - "bottom": 底部居中 (默认)
            - "center": 正中居中
        text_color (tuple): 文字颜色 (R, G, B)，默认白色
        bg_color (tuple): 背景颜色 (R, G, B, A)，默认半透明黑色
        font_path (str): TrueType 字体文件路径，None 使用默认字体

    返回:
        str: 输出图片路径

    异常:
        FileNotFoundError: 原始图片不存在
        Exception: 处理失败 (字体加载失败、图像格式错误等)
    """
    # 打开原始图片并转换为 RGBA (支持透明度)
    img = Image.open(image_path).convert("RGBA")

    # 创建与原图同样大小的透明叠加层
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 根据图片宽度自动计算字体大小 (图片宽度的 1/25)
    font_size = max(16, img.width // 25)

    # 按优先级尝试加载字体
    if font_path and os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        try:
            # 尝试 SimHei (Windows 中文字体)
            font = ImageFont.truetype("simhei.ttf", font_size)
        except OSError:
            try:
                # 尝试 Arial (英文通用字体)
                font = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                # 使用 Pillow 内置默认字体
                font = ImageFont.load_default()

    # 计算文字尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    padding = 10  # 文字与边框的内边距

    # 根据 position 参数计算文字坐标 (居中对齐)
    if position == "bottom":
        x = (img.width - text_width) // 2
        y = img.height - text_height - padding * 3
    elif position == "top":
        x = (img.width - text_width) // 2
        y = padding
    else:  # center
        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2

    # 绘制半透明背景矩形
    bg_x0 = x - padding
    bg_y0 = y - padding
    bg_x1 = x + text_width + padding
    bg_y1 = y + text_height + padding
    draw.rectangle([bg_x0, bg_y0, bg_x1, bg_y1], fill=bg_color)

    # 绘制文字
    draw.text((x, y), text, fill=text_color, font=font)

    # 合并叠加层到原图
    result = Image.alpha_composite(img, overlay)
    # 转换为 RGB (JPEG 不支持透明度) 并保存
    result = result.convert("RGB")
    result.save(output_path, "JPEG", quality=90)

    return output_path


def build_timestamp_text(custom_text: str = "") -> str:
    """
    构建带时间戳的文字

    参数:
        custom_text (str): 自定义前缀文字，为空则只显示时间

    返回:
        str: 格式化的文字
            - 有自定义文字: "自定义文字  |  2024-01-01 12:00:00"
            - 无自定义文字: "2024-01-01 12:00:00"
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if custom_text:
        return f"{custom_text}  |  {now}"
    return now
