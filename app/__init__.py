import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from .config_store import ConfigError, ConfigStore
from .frpc import FrpcManager

ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=256 * 1024,
        FRPC_CONFIG=os.environ.get("FRPC_CONFIG", str(ROOT / "frpc.toml")),
        APP_CONFIG=os.environ.get("APP_CONFIG", str(ROOT / "app_config.json")),
        FRPC_BIN=os.environ.get("FRPC_BIN", str(ROOT / "frp" / ("frpc.exe" if os.name == "nt" else "frpc"))),
        FRPC_LOG=os.environ.get("FRPC_LOG", str(ROOT / "logs" / "frpc.log")),
        FRPC_MANAGE=os.environ.get("FRPC_MANAGE", "0") == "1",
        FRONTEND_DIST=str(ROOT / "frontend" / "dist"),
    )
    if test_config:
        app.config.update(test_config)
    app.json.ensure_ascii = False
    from flask_compress import Compress
    app.config["COMPRESS_MIMETYPES"] = ["text/html", "text/css", "application/javascript", "text/javascript"]
    Compress(app)
    app.extensions["config_store"] = ConfigStore(app.config["FRPC_CONFIG"], app.config["APP_CONFIG"])
    app.extensions["frpc_manager"] = FrpcManager(app.config["FRPC_BIN"], app.config["FRPC_CONFIG"],
                                                  app.config["FRPC_LOG"], app.config["FRPC_MANAGE"])
    from .api import api
    app.register_blueprint(api)

    @app.errorhandler(ConfigError)
    def config_error(error):
        return jsonify(message=str(error), fields=error.fields), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(message=error.description, fields={}), error.code

    @app.after_request
    def headers(response):
        from flask import request
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.path.startswith("/api/") or response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/assets/<path:filename>")
    def assets(filename):
        response = send_from_directory(Path(app.config["FRONTEND_DIST"]) / "assets", filename)
        response.direct_passthrough = False
        response.make_sequence()  # Small hashed bundles: buffer to enable gzip as well as Brotli.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/favicon.svg")
    def favicon():
        return send_from_directory(Path(app.config["FRONTEND_DIST"]), "favicon.svg")

    @app.get("/")
    @app.get("/config")
    @app.get("/settings")
    @app.get("/logs")
    def frontend():
        dist = Path(app.config["FRONTEND_DIST"])
        if not (dist / "index.html").exists():
            return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>前端尚未构建</title>"
                    "<h1>请先构建前端</h1><p>在项目目录运行：<code>npm --prefix frontend ci</code>，"
                    "然后运行 <code>npm --prefix frontend run build</code>。</p>"
                    "<p>开发模式：运行 <code>npm --prefix frontend run dev</code> 并访问 http://127.0.0.1:5173。</p></html>", 503)
        response = send_from_directory(dist, "index.html")
        response.direct_passthrough = False
        response.make_sequence()
        return response

    return app
