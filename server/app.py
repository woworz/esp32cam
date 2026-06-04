"""
app.py - Flask 图片处理服务端

本模块是运行在 PC/服务器上的 Flask 应用，提供以下功能:
    1. 接收 ESP32 上传的图片
    2. 叠加文字时间戳
    3. 可选转发到其他服务器
    4. 提供可视化图片画廊
    5. 远程触发 ESP32 拍照
    6. 实时视频流预览

启动方式:
    cd server
    python app.py

依赖:
    - Flask: pip install flask
    - Pillow: pip install Pillow
    - requests: pip install requests (用于转发)
"""

import os
import uuid
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template_string
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

# 创建 Flask 应用实例
app = Flask(__name__)

# 确保存储目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)


@app.route("/upload", methods=["POST"])
def upload():
    """
    接收 ESP32 上传的图片

    请求格式: multipart/form-data
        - image: JPEG 图片文件
        - text:  标识文字 (可选)
        - position: 文字位置 (可选，默认 bottom)

    返回:
        成功:
        {
            "status": "ok",
            "message": "上传成功",
            "raw": "原始文件名",
            "processed": "处理后文件名",
            "text": "叠加的文字内容"
        }
        失败:
        {
            "status": "error",
            "message": "错误描述"
        }
    """
    # 检查是否包含图片文件
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "未找到图片文件"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "文件名为空"}), 400

    # 获取可选参数
    custom_text = request.form.get("text", "")  # 自定义标识文字
    position = request.form.get("position", TEXT_POSITION)  # 文字位置

    # 保存原始图片 (使用 UUID 防止文件名冲突)
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    raw_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(UPLOAD_FOLDER, raw_name)
    file.save(raw_path)

    # 处理图片: 叠加文字时间戳
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

    # 可选: 转发到其他服务器
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
    """
    获取指定图片

    优先从 processed 目录查找，其次从 uploads 目录查找。

    参数:
        filename (str): 图片文件名

    返回:
        成功: 图片文件 (image/jpeg)
        失败: 404 JSON 错误
    """
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": "图片不存在"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@app.route("/latest")
def latest():
    """
    获取最新的一张处理后图片

    返回:
        成功: 最新图片文件 (image/jpeg)
        失败: 404 JSON 错误
    """
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


@app.route("/api/images")
def api_images():
    """
    获取图片列表 (JSON API)

    返回:
        {
            "status": "ok",
            "count": 图片数量,
            "images": [
                {
                    "filename": "文件名",
                    "size": 文件大小(字节),
                    "created": 创建时间戳,
                    "url": "图片访问URL"
                },
                ...
            ]
        }
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
    # 按创建时间降序排序
    images.sort(key=lambda x: x["created"], reverse=True)
    return jsonify({
        "status": "ok",
        "count": len(images),
        "images": images,
    })


@app.route("/api/image/<filename>", methods=["DELETE"])
def api_delete_image(filename):
    """
    删除指定图片

    参数:
        filename (str): 图片文件名

    返回:
        成功: {"status": "ok", "message": "删除成功"}
        失败: {"status": "error", "message": "错误描述"}
    """
    # 尝试从 processed 目录删除
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"status": "ok", "message": "删除成功"})

    # 尝试从 uploads 目录删除
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"status": "ok", "message": "删除成功"})

    return jsonify({"status": "error", "message": "图片不存在"}), 404


@app.route("/api/stats")
def api_stats():
    """
    获取系统统计信息

    返回:
        {
            "status": "ok",
            "stats": {
                "processed_count": 处理后图片数量,
                "raw_count": 原始图片数量,
                "total_size": 总大小(字节),
                "esp32_configured": 是否配置了ESP32,
                "esp32_url": "ESP32地址"
            }
        }
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

    return jsonify({
        "status": "ok",
        "stats": {
            "processed_count": processed_count,
            "raw_count": raw_count,
            "total_size": total_size,
            "esp32_configured": ESP32_URL is not None,
            "esp32_url": ESP32_URL,
        },
    })


@app.route("/trigger", methods=["GET", "POST"])
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
    """
    照片画廊页面

    展示所有已处理的照片，支持点击查看大图、删除、远程触发拍照。
    页面每 10 秒自动刷新。
    """
    images = sorted(
        [f for f in os.listdir(PROCESSED_FOLDER) if f.endswith(".jpg")],
        key=lambda f: os.path.getmtime(os.path.join(PROCESSED_FOLDER, f)),
        reverse=True,
    )
    # 生成图片网格 HTML (最多显示 50 张)
    image_items = []
    for img in images[:50]:
        filepath = os.path.join(PROCESSED_FOLDER, img)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = os.path.getsize(filepath) / 1024
        image_items.append(f'''
        <div class="image-card" data-filename="{img}">
            <a href="/image/{img}" target="_blank" class="image-link">
                <img src="/image/{img}" loading="lazy" alt="{img}">
            </a>
            <div class="image-info">
                <span class="image-time">{mtime}</span>
                <span class="image-size">{size_kb:.1f}KB</span>
            </div>
            <button class="btn-delete" onclick="deleteImage('{img}')" title="删除">×</button>
        </div>''')
    image_grid = "\n".join(image_items)
    image_count = len(images)

    # ESP32 视频流卡片
    esp32_section = ""
    esp32_stream_url = ""
    if ESP32_URL:
        esp32_stream_url = ESP32_URL.replace("/capture", "/stream")
        esp32_base_url = ESP32_URL.replace("/capture", "/")
        esp32_section = f'''
    <div class="control-card">
        <div class="card-header">
            <span class="card-icon">📹</span>
            <h3>ESP32 实时预览</h3>
        </div>
        <div class="stream-container">
            <img id="esp32-stream" src="{esp32_stream_url}" alt="ESP32 Stream" onerror="this.src='/static/offline.png'">
            <div class="stream-overlay">
                <span class="live-badge">LIVE</span>
            </div>
        </div>
        <div class="card-actions">
            <a href="{esp32_base_url}" target="_blank" class="btn btn-secondary">打开全屏</a>
            <button class="btn btn-primary" onclick="triggerCapture()">远程拍照</button>
        </div>
    </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="10">
    <title>ESP32-CAM 可视化后端</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #eee;
            min-height: 100vh;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            border-bottom: 1px solid #2a2a4a;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .header h1 {{
            font-size: 22px;
            font-weight: 600;
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-badge {{
            background: #e94560;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .header-stats {{
            display: flex;
            gap: 20px;
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: #e94560;
        }}
        .stat-label {{
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
        }}
        
        /* Main Content */
        .main {{
            padding: 20px 24px;
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        /* Control Cards */
        .control-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .control-card {{
            background: #1a1a2e;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #2a2a4a;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
        }}
        .card-icon {{
            font-size: 20px;
        }}
        .card-header h3 {{
            font-size: 15px;
            font-weight: 500;
        }}
        .stream-container {{
            position: relative;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            aspect-ratio: 4/3;
        }}
        .stream-container img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        .stream-overlay {{
            position: absolute;
            top: 10px;
            left: 10px;
        }}
        .live-badge {{
            background: #e94560;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}
        .card-actions {{
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }}
        
        /* Stats Card */
        .stats-card {{
            background: linear-gradient(135deg, #1e3a5f 0%, #1a1a2e 100%);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-box .value {{
            font-size: 24px;
            font-weight: 600;
            color: #e94560;
        }}
        .stat-box .label {{
            font-size: 11px;
            color: #888;
            margin-top: 4px;
        }}
        
        /* Buttons */
        .btn {{
            padding: 10px 18px;
            border-radius: 8px;
            border: none;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-primary {{
            background: #e94560;
            color: white;
        }}
        .btn-primary:hover {{
            background: #c23152;
            transform: translateY(-1px);
        }}
        .btn-secondary {{
            background: #2a2a4a;
            color: #eee;
        }}
        .btn-secondary:hover {{
            background: #3a3a5a;
        }}
        .btn-danger {{
            background: #dc3545;
            color: white;
        }}
        .btn-danger:hover {{
            background: #c82333;
        }}
        
        /* Image Grid */
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }}
        .section-header h2 {{
            font-size: 18px;
            font-weight: 600;
        }}
        .image-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 16px;
        }}
        .image-card {{
            background: #1a1a2e;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
            transition: transform 0.2s, box-shadow 0.2s;
            border: 1px solid #2a2a4a;
        }}
        .image-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(233, 69, 96, 0.2);
        }}
        .image-link {{
            display: block;
            aspect-ratio: 4/3;
            overflow: hidden;
        }}
        .image-link img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }}
        .image-card:hover .image-link img {{
            transform: scale(1.05);
        }}
        .image-info {{
            padding: 10px 12px;
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #888;
        }}
        .btn-delete {{
            position: absolute;
            top: 8px;
            right: 8px;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: rgba(0,0,0,0.7);
            color: white;
            border: none;
            font-size: 18px;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.2s, background 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .image-card:hover .btn-delete {{
            opacity: 1;
        }}
        .btn-delete:hover {{
            background: #dc3545;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 80px 20px;
            color: #555;
        }}
        .empty-state .icon {{
            font-size: 48px;
            margin-bottom: 16px;
        }}
        .empty-state p {{
            font-size: 14px;
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 24px;
            font-size: 12px;
            color: #444;
            border-top: 1px solid #1a1a2e;
            margin-top: 40px;
        }}
        
        /* Toast Notification */
        .toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #1a1a2e;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            border-left: 4px solid #e94560;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transform: translateX(120%);
            transition: transform 0.3s;
            z-index: 1000;
        }}
        .toast.show {{
            transform: translateX(0);
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .header-stats {{
                width: 100%;
                justify-content: space-around;
            }}
            .control-cards {{
                grid-template-columns: 1fr;
            }}
            .image-grid {{
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <h1>📷 ESP32-CAM</h1>
            <span class="header-badge">可视化后端</span>
        </div>
        <div class="header-stats">
            <div class="stat-item">
                <div class="stat-value" id="photo-count">{image_count}</div>
                <div class="stat-label">照片总数</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="esp32-status">{"✅ 已连接" if ESP32_URL else "❌ 未配置"}</div>
                <div class="stat-label">ESP32 状态</div>
            </div>
        </div>
    </header>

    <main class="main">
        <div class="control-cards">
            {esp32_section}
            
            <div class="control-card stats-card">
                <div class="card-header">
                    <span class="card-icon">📊</span>
                    <h3>系统统计</h3>
                </div>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="value">{image_count}</div>
                        <div class="label">已处理</div>
                    </div>
                    <div class="stat-box">
                        <div class="value" id="raw-count">-</div>
                        <div class="label">原始图片</div>
                    </div>
                    <div class="stat-box">
                        <div class="value" id="total-size">-</div>
                        <div class="label">总大小</div>
                    </div>
                    <div class="stat-box">
                        <div class="value">ST7789</div>
                        <div class="label">TFT 屏幕</div>
                    </div>
                </div>
            </div>
            
            <div class="control-card">
                <div class="card-header">
                    <span class="card-icon">🔗</span>
                    <h3>API 接口</h3>
                </div>
                <div style="font-size: 12px; color: #888; line-height: 1.8;">
                    <code>POST /upload</code> - 上传图片<br>
                    <code>GET /api/images</code> - 图片列表<br>
                    <code>GET /api/stats</code> - 统计信息<br>
                    <code>GET /trigger</code> - 远程触发拍照
                </div>
                <div class="card-actions">
                    <button class="btn btn-secondary" onclick="loadStats()">刷新统计</button>
                </div>
            </div>
        </div>

        <div class="section-header">
            <h2>🖼️ 照片画廊</h2>
            <span style="color: #888; font-size: 13px;">每10秒自动刷新</span>
        </div>
        
        <div class="image-grid" id="image-grid">
            {image_grid or '<div class="empty-state"><div class="icon">📷</div><p>暂无照片，等待 ESP32 拍照上传...</p></div>'}
        </div>
    </main>

    <footer class="footer">
        ESP32-CAM 可视化后端 · OV3660 + ST7789 · Flask
    </footer>

    <div class="toast" id="toast"></div>

    <script>
        // 显示 Toast 通知
        function showToast(message, type = 'info') {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.borderLeftColor = type === 'error' ? '#dc3545' : '#e94560';
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        // 删除图片
        async function deleteImage(filename) {{
            if (!confirm('确定要删除这张图片吗？')) return;
            try {{
                const res = await fetch(`/api/image/${{filename}}`, {{ method: 'DELETE' }});
                const data = await res.json();
                if (data.status === 'ok') {{
                    showToast('删除成功');
                    document.querySelector(`[data-filename="${{filename}}"]`)?.remove();
                    // 更新计数
                    const countEl = document.getElementById('photo-count');
                    countEl.textContent = parseInt(countEl.textContent) - 1;
                }} else {{
                    showToast(data.message, 'error');
                }}
            }} catch (e) {{
                showToast('删除失败: ' + e.message, 'error');
            }}
        }}

        // 远程触发拍照
        async function triggerCapture() {{
            try {{
                showToast('正在触发拍照...');
                const res = await fetch('/trigger');
                const data = await res.json();
                if (data.status === 'ok') {{
                    showToast('拍照已触发，等待图片上传...');
                }} else {{
                    showToast(data.message, 'error');
                }}
            }} catch (e) {{
                showToast('触发失败: ' + e.message, 'error');
            }}
        }}

        // 加载统计信息
        async function loadStats() {{
            try {{
                const res = await fetch('/api/stats');
                const data = await res.json();
                if (data.status === 'ok') {{
                    const s = data.stats;
                    document.getElementById('raw-count').textContent = s.raw_count;
                    document.getElementById('total-size').textContent = formatSize(s.total_size);
                    showToast('统计已更新');
                }}
            }} catch (e) {{
                console.error('加载统计失败:', e);
            }}
        }}

        // 格式化文件大小
        function formatSize(bytes) {{
            if (bytes < 1024) return bytes + 'B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
            return (bytes / (1024 * 1024)).toFixed(2) + 'MB';
        }}

        // 页面加载时获取统计
        loadStats();
    </script>
</body>
</html>'''
    return html


if __name__ == "__main__":
    print(f"[Server] 启动服务 -> http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
