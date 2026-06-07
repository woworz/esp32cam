"""
api.py - REST API 路由蓝图

本模块定义所有 API 端点，使用 Flask Blueprint 组织。
所有端点仅返回 JSON，不包含任何 HTML 渲染。

端点列表:
    POST   /upload              - 上传图片
    GET    /image/<filename>    - 获取指定图片文件
    GET    /latest              - 获取最新图片文件
    GET    /api/images          - 获取图片列表 (JSON)
    DELETE /api/image/<filename>- 删除指定图片
    GET    /api/stats           - 获取统计信息 (JSON)
    GET    /trigger             - 远程触发 ESP32 拍照
    POST   /trigger             - 远程触发 ESP32 拍照
"""

import requests
from flask import Blueprint, request, jsonify, send_file
from services.image_service import (
    save_and_process_image,
    find_image_path,
    get_latest_processed_image,
    list_images,
    delete_image,
    get_stats,
)
from config import ESP32_URL

api_bp = Blueprint("api", __name__)


@api_bp.route("/upload", methods=["POST"])
def upload():
    """
    接收 ESP32 上传的图片

    请求格式: multipart/form-data
        - image:    JPEG 图片文件
        - text:     标识文字 (可选)
        - position: 文字位置 (可选，默认 bottom)

    返回:
        成功: {"status": "ok", "message": "上传成功", "raw": ..., "processed": ..., "text": ...}
        失败: {"status": "error", "message": "错误描述"}
    """
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "未找到图片文件"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "文件名为空"}), 400

    custom_text = request.form.get("text", "")
    position = request.form.get("position", "bottom")

    result = save_and_process_image(file, custom_text=custom_text, position=position)

    return jsonify({
        "status": "ok",
        "message": "上传成功",
        "raw": result["raw"],
        "processed": result["processed"],
        "text": result["text"],
    })


@api_bp.route("/image/<filename>")
def get_image(filename):
    """
    获取指定图片

    优先从 processed 目录查找，其次从 uploads 目录查找。

    参数:
        filename (str): 图片文件名

    返回:
        成功: 图片文件 (image/jpeg)
        失败: 404 JSON 错误
    """
    filepath = find_image_path(filename)
    if filepath is None:
        return jsonify({"status": "error", "message": "图片不存在"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@api_bp.route("/latest")
def latest():
    """
    获取最新的一张处理后图片

    返回:
        成功: 最新图片文件 (image/jpeg)
        失败: 404 JSON 错误
    """
    filepath = get_latest_processed_image()
    if filepath is None:
        return jsonify({"status": "error", "message": "暂无图片"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@api_bp.route("/api/images")
def api_images():
    """
    获取图片列表 (JSON API)

    返回:
        {
            "status": "ok",
            "count": 图片数量,
            "images": [
                {"filename": ..., "size": ..., "created": ..., "url": ...},
                ...
            ]
        }
    """
    images = list_images()
    return jsonify({
        "status": "ok",
        "count": len(images),
        "images": images,
    })


@api_bp.route("/api/image/<filename>", methods=["DELETE"])
def api_delete_image(filename):
    """
    删除指定图片

    参数:
        filename (str): 图片文件名

    返回:
        成功: {"status": "ok", "message": "删除成功"}
        失败: {"status": "error", "message": "图片不存在"}
    """
    if delete_image(filename):
        return jsonify({"status": "ok", "message": "删除成功"})
    return jsonify({"status": "error", "message": "图片不存在"}), 404


@api_bp.route("/api/stats")
def api_stats():
    """
    获取系统统计信息

    返回:
        {
            "status": "ok",
            "stats": {
                "processed_count": ...,
                "raw_count": ...,
                "total_size": ...,
                "esp32_configured": ...,
                "esp32_url": ...
            }
        }
    """
    stats = get_stats(esp32_url=ESP32_URL)
    return jsonify({
        "status": "ok",
        "stats": stats,
    })


@api_bp.route("/trigger", methods=["GET", "POST"])
def trigger_capture():
    """
    远程触发 ESP32 拍照

    通过 HTTP GET 请求触发 ESP32 的 /capture 接口。
    需要在 config.py 中配置 ESP32_URL。

    返回:
        成功: {"status": "ok", "message": "...", "esp32_response": {...}}
        失败: {"status": "error", "message": "错误描述"}
    """
    if not ESP32_URL:
        return jsonify({
            "status": "error",
            "message": "未配置 ESP32_URL，请在 config.py 中设置 ESP32 的拍照触发地址",
        }), 400

    try:
        resp = requests.get(ESP32_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({
            "status": "ok",
            "message": "已触发ESP32拍照",
            "esp32_response": data,
        })
    except requests.exceptions.ConnectError:
        return jsonify({
            "status": "error",
            "message": f"无法连接到ESP32: {ESP32_URL}",
        }), 502
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "ESP32响应超时",
        }), 504
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500
