"""Bounded per-process login throttling; use a shared gateway limit with multiple workers."""
from collections import deque
from threading import Lock
from time import monotonic
from flask import request


def install_login_throttle(app):
    attempts = {}
    lock = Lock()

    @app.before_request
    def throttle_login():
        if request.method != "POST" or request.path not in {"/api/auth/login", "/api/auth/register", "/api/auth/password/request", "/api/auth/password/reset", "/api/auth/verification/request", "/api/auth/verification/confirm"}:
            return None
        data = request.get_json(silent=True)
        email = data.get("email", "") if isinstance(data, dict) else ""
        if not isinstance(email, str):
            email = ""
        now = monotonic()
        address = request.remote_addr or "unknown"
        keys = [(address, "*"), (address, request.path + ":" + email.strip().lower()[:254])]
        with lock:
            for key, queue in list(attempts.items()):
                while queue and queue[0] <= now - 300:
                    queue.popleft()
                if not queue:
                    del attempts[key]
            for key, limit in zip(keys, (100, 20)):
                queue = attempts.get(key, ())
                if len(queue) >= limit:
                    retry = max(1, int(300 - (now - queue[0])) + 1)
                    return {"error": "操作过于频繁，请稍后重试"}, 429, {"Retry-After": str(retry)}
            if len(attempts) + sum(key not in attempts for key in keys) > 4096:
                return {"error": "账号服务繁忙，请稍后重试"}, 429, {"Retry-After": "300"}
            for key in keys:
                attempts.setdefault(key, deque()).append(now)
