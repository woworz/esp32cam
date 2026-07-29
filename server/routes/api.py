"""ESP-CAM 公网服务器 REST API。"""

from flask import Blueprint, jsonify, request, send_file

from config import DEFAULT_DEVICE_ID
from services.command_service import (
    claim_next_command,
    complete_command,
    create_capture_command,
    get_command,
    get_device_status,
)
from services.image_service import (
    delete_image,
    find_image_path,
    get_latest_processed_image,
    get_stats,
    list_images,
    save_and_process_image,
)


api_bp = Blueprint("api", __name__)


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok", "service": "esp-cam"})


@api_bp.route("/upload", methods=["POST"])
def upload():
    """接收 ESP32 上传的 JPEG，保存原图并生成带时间戳的处理图。"""
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "未找到图片文件"}), 400

    image_file = request.files["image"]
    if not image_file.filename:
        return jsonify({"status": "error", "message": "文件名为空"}), 400

    result = save_and_process_image(
        image_file,
        custom_text=request.form.get("text", ""),
        position=request.form.get("position", "bottom"),
    )
    return jsonify(
        {
            "status": "ok",
            "message": "上传成功",
            "raw": result["raw"],
            "processed": result["processed"],
            "text": result["text"],
            "device_id": request.form.get("device_id", DEFAULT_DEVICE_ID),
        }
    )


@api_bp.route("/image/<filename>")
def get_image(filename):
    filepath = find_image_path(filename)
    if filepath is None:
        return jsonify({"status": "error", "message": "图片不存在"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@api_bp.route("/download/<filename>")
def download_image(filename):
    """以附件形式下载服务器中的原图或处理图。"""
    filepath = find_image_path(filename)
    if filepath is None:
        return jsonify({"status": "error", "message": "图片不存在"}), 404
    return send_file(
        filepath,
        mimetype="image/jpeg",
        as_attachment=True,
        download_name=filename,
    )


@api_bp.route("/latest")
def latest():
    filepath = get_latest_processed_image()
    if filepath is None:
        return jsonify({"status": "error", "message": "暂无图片"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@api_bp.route("/api/images")
def api_images():
    images = list_images()
    return jsonify({"status": "ok", "count": len(images), "images": images})


@api_bp.route("/api/image/<filename>", methods=["DELETE"])
def api_delete_image(filename):
    if delete_image(filename):
        return jsonify({"status": "ok", "message": "删除成功"})
    return jsonify({"status": "error", "message": "图片不存在"}), 404


@api_bp.route("/api/stats")
def api_stats():
    stats = get_stats()
    stats.update(get_device_status(DEFAULT_DEVICE_ID))
    return jsonify({"status": "ok", "stats": stats})


@api_bp.route("/trigger", methods=["GET", "POST"])
def trigger_capture():
    """将拍照命令写入队列，由 ESP32 主动轮询领取。"""
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", DEFAULT_DEVICE_ID)
    command = create_capture_command(device_id)
    return (
        jsonify(
            {
                "status": "ok",
                "message": "拍照命令已进入队列",
                "command": command,
            }
        ),
        202,
    )


@api_bp.route("/api/device/commands/next")
def device_next_command():
    """设备心跳接口，同时领取下一条拍照命令。"""
    device_id = request.args.get("device_id", DEFAULT_DEVICE_ID)
    command = claim_next_command(device_id)
    return jsonify({"status": "ok", "command": command})


@api_bp.route("/api/commands/<command_id>")
def api_command_status(command_id):
    """供网页查询远程拍照命令的当前状态。"""
    command = get_command(command_id)
    if command is None:
        return jsonify({"status": "error", "message": "命令不存在"}), 404
    return jsonify({"status": "ok", "command": command})


@api_bp.route(
    "/api/device/commands/<command_id>/result",
    methods=["POST"],
)
def device_command_result(command_id):
    """接收设备回报的命令执行结果。"""
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", DEFAULT_DEVICE_ID)
    status = payload.get("status", "")
    try:
        command = complete_command(
            command_id,
            device_id,
            status,
            payload.get("message", ""),
        )
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    if command is None:
        return jsonify({"status": "error", "message": "命令不存在"}), 404
    return jsonify({"status": "ok", "command": command})
