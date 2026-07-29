"""
image_service.py - 图片业务逻辑服务层

本模块封装所有与图片相关的业务逻辑，包括:
    1. 图片保存与处理
    2. 图片列表查询
    3. 图片删除
    4. 统计信息计算

职责:
    - 被 routes/api.py 调用
    - 不直接处理 HTTP 请求/响应
"""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from utils.image_processor import add_text_overlay, build_timestamp_text
from config import (
    UPLOAD_FOLDER,
    PROCESSED_FOLDER,
    FONT_PATH,
    TEXT_POSITION,
    TEXT_COLOR,
    TEXT_BG_COLOR,
)


def save_and_process_image(
    file_storage,
    custom_text: str = "",
    position: str = TEXT_POSITION,
) -> Dict:
    """
    保存原始图片并处理（叠加文字时间戳）

    参数:
        file_storage: Flask FileStorage 对象
        custom_text (str): 自定义标识文字
        position (str): 文字位置

    返回:
        dict: 包含 raw, processed, text 等信息的字典
    """
    ext = os.path.splitext(file_storage.filename)[1] or ".jpg"
    raw_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(UPLOAD_FOLDER, raw_name)
    file_storage.save(raw_path)

    processed_name = f"{uuid.uuid4().hex}.jpg"
    processed_path = os.path.join(PROCESSED_FOLDER, processed_name)

    overlay_text = build_timestamp_text(custom_text)
    add_text_overlay(
        image_path=raw_path,
        text=overlay_text,
        output_path=processed_path,
        position=position,
        text_color=TEXT_COLOR,
        bg_color=TEXT_BG_COLOR,
        font_path=FONT_PATH,
    )

    return {
        "raw": raw_name,
        "processed": processed_name,
        "text": overlay_text,
    }


def find_image_path(filename: str) -> Optional[str]:
    """
    查找图片文件路径

    优先从 processed 目录查找，其次从 uploads 目录查找。

    参数:
        filename (str): 图片文件名

    返回:
        str: 图片完整路径，不存在则返回 None
    """
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(filepath):
        return filepath
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return filepath
    return None


def get_latest_processed_image() -> Optional[str]:
    """
    获取最新的一张处理后图片路径

    返回:
        str: 最新图片完整路径，不存在则返回 None
    """
    if not os.path.exists(PROCESSED_FOLDER):
        return None

    processed_files = sorted(
        [f for f in os.listdir(PROCESSED_FOLDER) if f.endswith(".jpg")],
        key=lambda f: os.path.getmtime(os.path.join(PROCESSED_FOLDER, f)),
        reverse=True,
    )
    if not processed_files:
        return None
    return os.path.join(PROCESSED_FOLDER, processed_files[0])


def list_images() -> List[Dict]:
    """
    获取所有处理后图片的列表

    返回:
        list: 按创建时间降序排列的图片信息字典列表
    """
    images = []
    if os.path.exists(PROCESSED_FOLDER):
        for f in os.listdir(PROCESSED_FOLDER):
            if f.endswith(".jpg"):
                filepath = os.path.join(PROCESSED_FOLDER, f)
                stat = os.stat(filepath)
                images.append({
                    "filename": f,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/image/{f}",
                })
    images.sort(key=lambda x: x["created"], reverse=True)
    return images


def delete_image(filename: str) -> bool:
    """
    删除指定图片

    优先从 processed 目录删除，其次从 uploads 目录删除。

    参数:
        filename (str): 图片文件名

    返回:
        bool: 是否删除成功
    """
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except OSError:
            return False

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except OSError:
            return False

    return False


def get_stats() -> Dict:
    """
    获取系统统计信息

    参数:
    返回:
        dict: 包含 processed_count, raw_count, total_size 的字典
    """
    processed_count = 0
    raw_count = 0
    total_size = 0

    if os.path.exists(PROCESSED_FOLDER):
        for f in os.listdir(PROCESSED_FOLDER):
            if f.endswith(".jpg"):
                processed_count += 1
                total_size += os.path.getsize(os.path.join(PROCESSED_FOLDER, f))

    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            if f.endswith(".jpg"):
                raw_count += 1
                total_size += os.path.getsize(os.path.join(UPLOAD_FOLDER, f))

    return {
        "processed_count": processed_count,
        "raw_count": raw_count,
        "total_size": total_size,
    }
