"""Validated, revision-aware access to the existing TOML and display metadata files."""
from __future__ import annotations

import copy
import errno
import hashlib
import ipaddress
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

import toml


class ConfigError(Exception):
    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.status = status
        self.fields = fields or {}


def valid_host(value):
    if not isinstance(value, str) or not value or len(value) > 253:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part)
                   for part in value.rstrip(".").split("."))


def validate_proxy(data):
    errors = {}
    for key, label, limit in (("name", "代理名称", 100), ("display_name", "显示名称", 100),
                              ("group", "分组", 50), ("access_url", "访问地址", 2048)):
        value = data.get(key, "")
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
            errors[key] = f"{label}格式不正确或超过 {limit} 个字符"
    if not isinstance(data.get("name"), str) or not re.fullmatch(r"[\w.-]{1,100}", data.get("name", "")):
        errors["name"] = "使用 1–100 个字母、数字、中文、下划线、短横线或点"
    if data.get("type") not in ("tcp", "udp"):
        errors["type"] = "当前可视化编辑支持 TCP 和 UDP"
    if not valid_host(data.get("local_ip")):
        errors["local_ip"] = "请输入有效的 IP 地址或主机名，不含协议和端口"
    for key in ("local_port", "remote_port"):
        value = data.get(key)
        if type(value) is not int or not 1 <= value <= 65535:
            errors[key] = "端口必须是 1–65535 的整数"
    for key in ("visible", "favorite"):
        if type(data.get(key, False)) is not bool:
            errors[key] = "必须为布尔值"
    url = data.get("access_url", "")
    if isinstance(url, str) and url:
        try:
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not valid_host(parsed.hostname)
                    or parsed.username is not None or parsed.password is not None
                    or "\\" in url or any(c.isspace() for c in url)):
                raise ValueError()
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError()
        except ValueError:
            errors["access_url"] = "请输入完整的 HTTP/HTTPS 地址，不含用户名和密码"
    if errors:
        raise ConfigError("请检查标记的字段", fields=errors)


class ConfigStore:
    def __init__(self, frpc_path, app_path):
        self.frpc_path = Path(frpc_path)
        self.app_path = Path(app_path)
        self.lock = threading.RLock()

    def _read(self):
        try:
            raw_frpc = self.frpc_path.read_bytes()
            raw_app = self.app_path.read_bytes() if self.app_path.exists() else b'{}'
            config = toml.loads(raw_frpc.decode("utf-8-sig"))
            meta = json.loads(raw_app.decode("utf-8-sig"))
            proxies = config.get("proxies", [])
            if (not isinstance(proxies, list) or not all(isinstance(p, dict) and isinstance(p.get("name"), str) for p in proxies)
                    or not isinstance(meta, dict) or not isinstance(meta.get("proxies_display", {}), dict)):
                raise ValueError("invalid shape")
            if any(not isinstance(value, dict) for value in meta.get("proxies_display", {}).values()):
                raise ValueError("invalid display settings")
        except (OSError, ValueError, TypeError) as exc:
            raise ConfigError("无法读取配置，请检查文件是否存在且 TOML/JSON 格式正确；未覆盖原文件", 500) from exc
        revision = hashlib.sha256(raw_frpc + b"\0" + raw_app).hexdigest()
        frpc_revision = hashlib.sha256(raw_frpc).hexdigest()
        return config, meta, revision, frpc_revision

    def state(self):
        with self.lock:
            config, meta, revision, frpc_revision = self._read()
            proxies = []
            for proxy in config.get("proxies", []):
                display = meta.get("proxies_display", {}).get(proxy["name"], {})
                proxies.append({
                    "name": proxy["name"], "type": proxy.get("type", "tcp"),
                    "local_ip": proxy.get("localIP", "127.0.0.1"),
                    "local_port": proxy.get("localPort"), "remote_port": proxy.get("remotePort"),
                    "display_name": display.get("displayName") or proxy["name"],
                    "visible": display.get("visible", True), "group": display.get("group", ""),
                    "favorite": display.get("favorite", False), "access_url": display.get("accessUrl", ""),
                    "editable": proxy.get("type", "tcp") in ("tcp", "udp"),
                })
            return {"proxies": proxies, "target_ip": meta.get("target_ip", "127.0.0.1"),
                    "revision": revision, "frpc_revision": frpc_revision}

    def check_revision(self, revision):
        if not revision or revision != self._read()[2]:
            raise ConfigError("配置已被其他页面或程序修改。请刷新后重试；本次修改未保存", 409)

    @staticmethod
    def _write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                os.chmod(temp, path.stat().st_mode & 0o777)
            try:
                os.replace(temp, path)
            except OSError as exc:
                # Existing Docker deployments bind-mount individual config files.
                # Such mount points cannot be replaced; preserve that compatibility.
                if exc.errno != errno.EBUSY:
                    raise
                with path.open("wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def _save(self, config=None, meta=None):
        updates = []
        if config is not None:
            updates.append((self.frpc_path, toml.dumps(config).encode("utf-8")))
        if meta is not None:
            updates.append((self.app_path, (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")))
        originals = [(path, path.read_bytes() if path.exists() else None) for path, _ in updates]
        try:
            for path, content in updates:
                self._write(path, content)
        except OSError as exc:
            rollback_failed = False
            for path, original in originals:
                try:
                    if original is not None:
                        self._write(path, original)
                    elif path.exists():
                        path.unlink()
                except OSError:
                    rollback_failed = True
            message = "保存失败，请检查文件权限和磁盘空间"
            if rollback_failed:
                message += "；回滚也失败，请人工检查两份配置的一致性"
            raise ConfigError(message, 500) from exc

    def save_proxy(self, data, revision, original_name=None):
        validate_proxy(data)
        with self.lock:
            self.check_revision(revision)
            config, meta, _, _ = self._read()
            proxies = config.setdefault("proxies", [])
            original = next((p for p in proxies if p["name"] == original_name), None)
            if original_name is not None and original is None:
                raise ConfigError("代理不存在", 404)
            if original is not None and original.get("type", "tcp") not in ("tcp", "udp"):
                raise ConfigError("此协议暂不支持可视化编辑；原配置已保留")
            if any(p["name"] == data["name"] and p is not original for p in proxies):
                raise ConfigError("代理名称已存在", fields={"name": "请使用不同的代理名称"})
            if any(p is not original and p.get("type", "tcp") == data["type"]
                   and p.get("remotePort") == data["remote_port"] for p in proxies):
                raise ConfigError("同协议的远程端口已被当前配置使用", fields={"remote_port": "请更换端口；TCP/UDP 可共用同一数字端口"})
            updated = copy.deepcopy(original) if original is not None else {}
            updated.update(name=data["name"], type=data["type"], localIP=data["local_ip"],
                           localPort=data["local_port"], remotePort=data["remote_port"])
            frpc_changed = original != updated
            if original is None:
                proxies.append(updated)
            else:
                proxies[proxies.index(original)] = updated
            displays = meta.setdefault("proxies_display", {})
            display = displays.pop(original_name, {}) if original_name else {}
            display.update(displayName=data.get("display_name") or data["name"], visible=data.get("visible", True),
                           group=data.get("group", ""), favorite=data.get("favorite", False), accessUrl=data.get("access_url", ""))
            displays[data["name"]] = display
            self._save(config=config if frpc_changed else None, meta=meta)
            return self.state()

    def delete_proxy(self, name, revision):
        with self.lock:
            self.check_revision(revision)
            config, meta, _, _ = self._read()
            proxies = config.get("proxies", [])
            if not any(p["name"] == name for p in proxies):
                raise ConfigError("代理不存在", 404)
            config["proxies"] = [p for p in proxies if p["name"] != name]
            meta.setdefault("proxies_display", {}).pop(name, None)
            self._save(config, meta)
            return self.state()

    def save_settings(self, data, revision):
        if not valid_host(data.get("target_ip")):
            raise ConfigError("请输入有效的 IP 地址或主机名", fields={"target_ip": "不含协议、端口或路径"})
        with self.lock:
            self.check_revision(revision)
            _, meta, _, _ = self._read()
            meta["target_ip"] = data["target_ip"]
            self._save(meta=meta)
            return self.state()
