from functools import wraps
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, session

from .config_store import ConfigError

api = Blueprint("api", __name__, url_prefix="/api")


def store():
    return current_app.extensions["config_store"]


def manager():
    return current_app.extensions["frpc_manager"]


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ConfigError("请求必须为 JSON 对象")
    return data


def protect_write(view):
    @wraps(view)
    def protected(*args, **kwargs):
        token = session.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, request.headers.get("X-CSRF-Token", "")):
            raise ConfigError("会话已过期，请刷新页面后重试", 403)
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise ConfigError("拒绝跨站修改请求", 403)
        return view(*args, **kwargs)
    return protected


def response_state(state=None):
    state = state or store().state()
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {**state, "csrf_token": session["csrf_token"], "runtime": manager().status(state["frpc_revision"])}


@api.get("/state")
def state():
    return jsonify(response_state())


@api.post("/proxies")
@protect_write
def add_proxy():
    data = payload()
    return jsonify(response_state(store().save_proxy(data, data.get("revision")))), 201


@api.put("/proxies/<path:name>")
@protect_write
def edit_proxy(name):
    data = payload()
    return jsonify(response_state(store().save_proxy(data, data.get("revision"), name)))


@api.delete("/proxies/<path:name>")
@protect_write
def delete_proxy(name):
    data = payload()
    return jsonify(response_state(store().delete_proxy(name, data.get("revision"))))


@api.put("/proxy-groups")
@protect_write
def proxy_groups():
    data = payload()
    return jsonify(response_state(store().save_groups(data, data.get("revision"))))


@api.put("/settings")
@protect_write
def settings():
    data = payload()
    return jsonify(response_state(store().save_settings(data, data.get("revision"))))


@api.get("/runtime")
def runtime():
    state = store().state()
    return jsonify(manager().status(state["frpc_revision"]))


@api.post("/runtime/apply")
@protect_write
def apply():
    data = payload()
    with store().lock:
        store().check_revision(data.get("revision"))
        manager().apply(store().state()["frpc_revision"])
        return jsonify(response_state())


@api.get("/logs")
def logs():
    return jsonify(manager().logs())
