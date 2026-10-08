import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    from waitress import serve

    manager = app.extensions["frpc_manager"]
    if os.environ.get("FRPC_AUTOSTART", "0") == "1":
        try:
            manager.apply(app.extensions["config_store"].state()["frpc_revision"])
        except Exception as exc:
            app.logger.error("frpc 自动启动失败：%s", exc)
    try:
        serve(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")), threads=4)
    finally:
        manager.close()
