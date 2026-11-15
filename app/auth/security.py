"""Session and role checks at the HTTP boundary."""

from functools import wraps

from flask import session, request

from app.auth.repository import find_role
from app.infrastructure.database import get_db


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return {"error": "请先登录"}, 401
        user = find_role(get_db(), session["user_id"])
        if not user or user.get("session_version", 0) != session.get("session_version", 0):
            session.clear()
            return {"error": "登录已失效，请重新登录"}, 401
        if user.get("verification_required") and not user.get("email_verified_at") and request.path not in {"/api/auth/verification/request", "/api/profile", "/api/profile/password"}:
            return {"error": "请先验证邮箱，再使用学习和教学功能", "code": "email_unverified"}, 403
        return view(*args, **kwargs)

    return wrapped


def roles_required(roles, message):
    def decorate(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = find_role(get_db(), session["user_id"])
            if not user or user["role"] not in roles:
                return {"error": message}, 403
            return view(*args, **kwargs)

        return wrapped

    return decorate


admin_required = roles_required({"admin"}, "需要管理员权限")
teacher_or_admin_required = roles_required(
    {"teacher", "admin"}, "只有教师或管理员可以上传课程"
)
