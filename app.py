from __future__ import annotations

import json
import os
import socket
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values, set_key

from douyin_service import (
    PROJECT_ROOT,
    DouyinServiceError,
    cookie_map,
    fetch_creator_comments,
    fetch_video_comments,
    load_config,
    normalize_cookie,
    send_private_message,
    validate_cookie,
)


STATIC_ROOT = PROJECT_ROOT / "static"
MAX_BODY_SIZE = 1_000_000
TASKS: dict[str, threading.Event] = {}
CANCELLED_TASKS: set[str] = set()
TASKS_LOCK = threading.Lock()


def register_task(task_id: str) -> threading.Event:
    event = threading.Event()
    if task_id:
        with TASKS_LOCK:
            if task_id in CANCELLED_TASKS:
                event.set()
            TASKS[task_id] = event
    return event


def cancel_task(task_id: str) -> bool:
    with TASKS_LOCK:
        event = TASKS.get(task_id)
        if event is None and task_id:
            CANCELLED_TASKS.add(task_id)
    if event is None:
        return bool(task_id)
    event.set()
    return True


def finish_task(task_id: str) -> None:
    if task_id:
        with TASKS_LOCK:
            TASKS.pop(task_id, None)
            CANCELLED_TASKS.discard(task_id)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "DouyinLocalTool/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._serve_file(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/api/config":
            config = load_config()
            values = cookie_map(config.cookie)
            self._json(
                {
                    "ok": True,
                    "data": {
                        "cookie_configured": bool(config.cookie),
                        "cookie": config.cookie,
                        "cookie_valid_shape": all(
                            values.get(key) for key in ("sessionid", "s_v_web_id")
                        ),
                        "cookie_source": config.cookie_source,
                        "messaging_ready": config.messaging_ready,
                    },
                }
            )
            return
        if self.path == "/api/health":
            self._json({"ok": True, "data": {"status": "healthy"}})
            return
        self._json_error("页面不存在", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        routes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "/api/cookie": self._save_cookie,
            "/api/comments/video": self._video_comments,
            "/api/comments/creator": self._creator_comments,
            "/api/messages/send": self._send_message,
            "/api/tasks/cancel": self._cancel_task,
        }
        action = routes.get(self.path)
        if action is None:
            self._json_error("接口不存在", HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            data = action(payload)
            self._json({"ok": True, "data": data})
        except DouyinServiceError as exc:
            self._json_error(str(exc), HTTPStatus.BAD_REQUEST)
        except json.JSONDecodeError:
            self._json_error("请求不是有效的 JSON", HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            print(f"Unhandled error: {exc!r}")
            self._json_error("本地服务处理失败，请查看终端日志", HTTPStatus.INTERNAL_SERVER_ERROR)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise DouyinServiceError("无效的请求长度") from exc
        if length <= 0 or length > MAX_BODY_SIZE:
            raise DouyinServiceError("请求内容为空或过大")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise DouyinServiceError("请求内容必须是对象")
        return payload

    def _save_cookie(self, payload: dict[str, Any]) -> dict[str, Any]:
        cookie = normalize_cookie(str(payload.get("cookie") or ""))
        validate_cookie(cookie)
        env_path = PROJECT_ROOT / ".env"
        if not env_path.exists():
            env_path.touch()
        set_key(str(env_path), "DY_COOKIES", cookie, quote_mode="always")
        return {
            "saved": True,
            "cookie_source": str(env_path),
            "message": "Cookie 已保存，后续请求立即生效",
        }

    def _video_comments(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("request_id") or "")
        cancel_event = register_task(task_id)
        try:
            return fetch_video_comments(
                payload.get("url", ""),
                payload.get("limit", 50),
                cancel_event,
            )
        finally:
            finish_task(task_id)

    def _creator_comments(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("request_id") or "")
        cancel_event = register_task(task_id)
        try:
            return fetch_creator_comments(
                payload.get("url", ""),
                payload.get("video_limit", 10),
                payload.get("total_comment_limit", 100),
                cancel_event,
            )
        finally:
            finish_task(task_id)

    def _cancel_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(payload.get("request_id") or "")
        return {"cancelled": cancel_task(task_id)}

    def _send_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        return send_private_message(payload.get("user_id"), payload.get("content"))

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._json_error("页面文件不存在", HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json_error(self, message: str, status: HTTPStatus) -> None:
        self._json({"ok": False, "error": message}, status)


def find_available_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 21):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"端口 {preferred}–{preferred + 20} 均不可用")


def main() -> None:
    env = dotenv_values(PROJECT_ROOT / ".env")
    host = str(os.getenv("APP_HOST") or env.get("APP_HOST") or "127.0.0.1")
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("出于 Cookie 安全考虑，APP_HOST 只能使用 127.0.0.1 或 localhost")
    try:
        preferred_port = int(os.getenv("APP_PORT") or env.get("APP_PORT") or "8765")
    except ValueError as exc:
        raise RuntimeError("APP_PORT 必须是整数") from exc
    port = find_available_port(host, preferred_port)
    server = ThreadingHTTPServer((host, port), AppHandler)
    url = f"http://{host}:{port}/"
    print(f"抖音评论私信工具已启动：{url}")
    print("按 Ctrl+C 停止服务")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务…")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
