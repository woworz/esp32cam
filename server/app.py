import os
import uuid
import requests
from flask import Flask, request, jsonify, send_file
from config import (
    HOST,
    PORT,
    UPLOAD_FOLDER,
    PROCESSED_FOLDER,
    FORWARD_URL,
    ESP32_URL,
    FONT_PATH,
    TEXT_POSITION,
    TEXT_COLOR,
    TEXT_BG_COLOR,
)
from utils.image_processor import add_text_overlay, build_timestamp_text

app = Flask(__name__)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "未找到图片文件"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "文件名为空"}), 400

    custom_text = request.form.get("text", "")
    position = request.form.get("position", TEXT_POSITION)

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    raw_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(UPLOAD_FOLDER, raw_name)
    file.save(raw_path)

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

    if FORWARD_URL:
        try:
            with open(processed_path, "rb") as f:
                requests.post(
                    FORWARD_URL,
                    files={"image": (processed_name, f, "image/jpeg")},
                    timeout=10,
                )
        except Exception as e:
            app.logger.warning(f"转发失败: {e}")

    return jsonify(
        {
            "status": "ok",
            "message": "上传成功",
            "raw": raw_name,
            "processed": processed_name,
            "text": overlay_text,
        }
    )


@app.route("/image/<filename>")
def get_image(filename):
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": "图片不存在"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@app.route("/latest")
def latest():
    processed_files = sorted(
        [f for f in os.listdir(PROCESSED_FOLDER) if f.endswith(".jpg")],
        key=lambda f: os.path.getmtime(os.path.join(PROCESSED_FOLDER, f)),
        reverse=True,
    )
    if not processed_files:
        return jsonify({"status": "error", "message": "暂无图片"}), 404
    return send_file(
        os.path.join(PROCESSED_FOLDER, processed_files[0]), mimetype="image/jpeg"
    )


@app.route("/trigger", methods=["GET", "POST"])
def trigger_capture():
    if not ESP32_URL:
        return jsonify({"status": "error", "message": "未配置 ESP32_URL，请在 config.py 中设置 ESP32 的拍照触发地址"}), 400

    try:
        resp = requests.get(ESP32_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({"status": "ok", "message": "已触发ESP32拍照", "esp32_response": data})
    except requests.exceptions.ConnectError:
        return jsonify({"status": "error", "message": f"无法连接到ESP32: {ESP32_URL}"}), 502
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "ESP32响应超时"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
@app.route("/gallery")
def gallery():
    images = sorted(
        [f for f in os.listdir(PROCESSED_FOLDER) if f.endswith(".jpg")],
        key=lambda f: os.path.getmtime(os.path.join(PROCESSED_FOLDER, f)),
        reverse=True,
    )
    image_items = "\n".join(
        f'<div class="item"><a href="/image/{img}" target="_blank"><img src="/image/{img}" loading="lazy"></a></div>'
        for img in images[:20]
    )
    image_count = len(images)
    esp32_section = ""
    if ESP32_URL:
        esp32_section = f'''
    <div class="card">
      <h2>📡 ESP32 实时视频流</h2>
      <p class="sub">打开以下地址查看实时MJPEG画面</p>
      <p class="url"><a href="{ESP32_URL.replace("/capture", "")}" target="_blank">{ESP32_URL.replace("/capture", "/")}</a></p>
    </div>'''

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="10">
<title>ESP32-CAM 照片库</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#0f0f0f;color:#eee;min-height:100vh}}
.header{{background:#1a1a1a;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}}
.header h1{{font-size:20px}}
.stats{{font-size:13px;color:#888}}
.cards{{display:flex;gap:12px;padding:16px 20px;flex-wrap:wrap}}
.card{{background:#1a1a1a;border-radius:10px;padding:18px 20px;flex:1;min-width:250px}}
.card h2{{font-size:15px;margin-bottom:8px}}
.card .sub{{font-size:12px;color:#888}}
.card .url{{margin-top:6px;font-size:13px}}
.card .url a{{color:#e94560;text-decoration:none}}
.card .btn{{display:inline-block;margin-top:10px;padding:8px 18px;background:#e94560;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer;text-decoration:none}}
.card .btn:hover{{background:#c23152}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;padding:0 20px 20px}}
.item{{background:#1a1a1a;border-radius:8px;overflow:hidden}}
.item img{{width:100%;display:block}}
.empty{{text-align:center;color:#555;padding:60px 20px}}
.footer{{text-align:center;padding:20px;font-size:12px;color:#444}}
</style>
</head>
<body>
<div class="header">
<h1>📷 ESP32-CAM 照片库</h1>
<span class="stats">共 {image_count} 张照片</span>
</div>
<div class="cards">
  <div class="card">
    <h2>🖼️ 处理后的照片</h2>
    <p class="sub">已叠加文字时间戳</p>
    <p class="sub">最近更新: {image_items[:1] and '有' or '无'}</p>
  </div>
  <div class="card">
    <h2>📤 上传端</h2>
    <p class="sub">ESP32 POST到 /upload 接口</p>
    <p class="url"><code>POST /upload</code> (multipart)</p>
  </div>
  {esp32_section}
</div>
<div class="grid">
{image_items or '<div class="empty">暂无照片，等待ESP32拍照上传...</div>'}
</div>
<div class="footer">每10秒自动刷新 · ESP32-CAM Project</div>
</body>
</html>"""
    return html


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=True)
