"""HTTP entry points for auth."""

from flask import Blueprint, request, session

from app.auth import service
from app.auth.security import admin_required, login_required
from app.infrastructure.database import get_db

bp = Blueprint("auth", __name__)


@bp.get("/api/auth/me")
def me():
    result = service.me(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.get("/api/admin/users")
@admin_required
def admin_users():
    result = service.admin_users(get_db=get_db)
    return result


@bp.post("/api/auth/register")
def register():
    result = service.register(
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    body = result[0] if isinstance(result, tuple) else result
    if "user" in body:
        session["user_id"] = body["user"]["id"]
    return result


@bp.post("/api/auth/login")
def login():
    result = service.login(data=request.get_json(silent=True), get_db=get_db)
    body = result[0] if isinstance(result, tuple) else result
    if "user" in body:
        session["user_id"] = body["user"]["id"]
    return result


@bp.post("/api/auth/logout")
def logout():
    result = service.logout()
    session.clear()
    return result


@bp.delete("/api/profile")
@login_required
def delete_account():
    result = service.delete_account(user_id=session.get("user_id"), get_db=get_db)
    if not isinstance(result, tuple) or result[1] == 404:
        session.clear()
    return result


@bp.patch("/api/profile")
@login_required
def update_profile():
    result = service.update_profile(
        user_id=session.get("user_id"),
        form=request.form,
        files=request.files,
        get_db=get_db,
    )
    return result


@bp.patch("/api/profile/password")
@login_required
def update_password():
    result = service.update_password(
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result
