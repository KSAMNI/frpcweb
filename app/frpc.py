"""Single-process FRPC ownership. Importing or constructing the app never starts FRPC."""
from __future__ import annotations

import atexit
import os
import subprocess
import threading
from pathlib import Path

from .config_store import ConfigError


class FrpcManager:
    def __init__(self, binary, config_path, log_path, enabled=False):
        self.binary = str(Path(binary).resolve())
        self.config_path = str(Path(config_path).resolve())
        self.log_path = Path(log_path)
        self.enabled = enabled
        self.process = None
        self.applied_revision = None
        self.last_error = None
        self.observed_revision = None
        self.dirty = False
        self.lock = threading.RLock()
        atexit.register(self.close)

    def status(self, revision):
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            if self.observed_revision is not None and self.observed_revision != revision:
                self.dirty = True
            self.observed_revision = revision
            return {"managed": self.enabled, "running": running,
                    "apply_state": ("pending" if self.dirty and self.applied_revision != revision else
                                    "unknown" if self.applied_revision is None else
                                    "applied" if self.applied_revision == revision and running else "pending"),
                    "last_error": self.last_error}

    def apply(self, revision):
        with self.lock:
            if not self.enabled:
                raise ConfigError("本地安全模式未启用进程管理。配置可以保存；设置 FRPC_MANAGE=1 后才允许应用", 403)
            if not Path(self.binary).is_file():
                raise ConfigError("找不到 frpc 可执行文件，请设置 FRPC_BIN", 503)
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            try:
                check = subprocess.run([self.binary, "verify", "-c", self.config_path],
                                       capture_output=True, timeout=15, **kwargs)
                if check.returncode:
                    raise ConfigError("frpc 配置校验失败，原进程未停止。请检查配置或 frpc 版本", 422)
                self.close()
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("ab") as log:
                    log.write(b"\n--- FRP Console: applying saved configuration ---\n")
                    log.flush()
                    self.process = subprocess.Popen([self.binary, "-c", self.config_path],
                                                    stdout=log, stderr=subprocess.STDOUT, **kwargs)
                try:
                    code = self.process.wait(timeout=0.5)
                    raise ConfigError(f"frpc 启动后退出（退出码 {code}），请查看日志", 502)
                except subprocess.TimeoutExpired:
                    pass
                self.applied_revision = revision
                self.last_error = None
                self.observed_revision = revision
                self.dirty = False
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.last_error = "frpc 启动或校验失败，请检查可执行文件与日志"
                raise ConfigError(self.last_error, 502) from exc
            except ConfigError as exc:
                self.last_error = str(exc)
                raise
            return self.status(revision)

    def close(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None

    def logs(self):
        try:
            with self.log_path.open("rb") as log:
                log.seek(0, os.SEEK_END)
                size = log.tell()
                log.seek(max(0, size - 32768))
                return {"log": log.read(32768).decode("utf-8", errors="replace"), "truncated": size > 32768}
        except FileNotFoundError:
            return {"log": "暂无日志。应用配置并启动 frpc 后，日志会显示在这里。", "truncated": False}
        except OSError as exc:
            raise ConfigError("无法读取日志，请检查文件权限", 500) from exc
