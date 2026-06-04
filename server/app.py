"""
app.py - Flask 应用工厂

本模块提供 create_app() 工厂函数，用于创建和配置 Flask 应用实例。
采用 Application Factory + Blueprint 的分层架构:
    - app.py:      应用工厂、配置注册
    - routes/api:  HTTP 路由层 (Blueprint)
    - services/:    业务逻辑层
    - utils/:       工具模块

启动方式:
    cd server
    python app.py

依赖:
    - Flask:      pip install flask
    - Pillow:     pip install Pillow
    - requests:   pip install requests
    - flask-cors: pip install flask-cors
"""

import os
from flask import Flask
from flask_cors import CORS
from config import (
    HOST,
    PORT,
    UPLOAD_FOLDER,
    PROCESSED_FOLDER,
    CORS_ORIGINS,
)
from routes.api import api_bp


def create_app() -> Flask:
    """
    应用工厂函数

    创建 Flask 应用实例，注册 Blueprint，配置 CORS，
    并确保必要的存储目录存在。

    返回:
        Flask: 配置好的 Flask 应用实例
    """
    app = Flask(__name__)

    # 注册 API Blueprint
    app.register_blueprint(api_bp)

    # 配置 CORS
    CORS(app, origins=CORS_ORIGINS)

    # 确保存储目录存在
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    return app


# 兼容旧启动方式: 直接运行 app.py 时创建应用
app = create_app()


if __name__ == "__main__":
    print(f"[Server] 启动服务 -> http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
