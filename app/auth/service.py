"""Auth business rules. HTTP parsing and session changes belong to routes."""

from secrets import token_hex
import re

from psycopg.errors import UniqueViolation
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import repository
from app.auth.serializers import user_json
from app.infrastructure.storage import allowed_file, upload_folder
from config import AVATAR_EXTENSIONS


def me(*, user_id, get_db):
    if not user_id:
        return {"user": None}
    user = repository.find_public_user(get_db(), (user_id,))
    from flask import session
    if user and user.get("session_version", 0) != session.get("session_version", 0):
        return {"user": None}
    return {"user": user_json(user) if user else None}


def admin_users(*, get_db):
    db = get_db()
    users = repository.list_accounts(db)
    user_data = {
        user["id"]: {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "created_at": user["created_at"],
            "courses": [],
            "learning_records": [],
        }
        for user in users
    }
    courses = repository.list_owned_courses(db)
    for course in courses:
        user_data[course["owner_id"]]["courses"].append(dict(course))
    learning_records = repository.list_learning_records(db)
    for record in learning_records:
        user_data[record["user_id"]]["learning_records"].append(dict(record))
    return {"users": list(user_data.values())}


def register(*, data, get_db):
    if not isinstance(data, dict):
        return ({"error": "请提交有效的表单对象"}, 400)
    if any(not isinstance(data.get(key, ""), str) for key in ("name", "email", "password", "role")):
        return ({"error": "注册信息格式不正确"}, 400)
    name = data.get("name", "").strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "student")).strip().lower()
    if not 1 <= len(name) <= 40 or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not 6 <= len(password) <= 128 or not password.strip():
        return ({"error": "请填写 1–40 字昵称、有效邮箱和 6–128 位非空白密码"}, 400)
    if role not in {"student", "teacher"}:
        return ({"error": "请选择学生或教师角色"}, 400)
    db = get_db()
    try:
        cursor = repository.insert_user(
            db, (name, email, generate_password_hash(password), role)
        )
        user_id = cursor.fetchone()["id"]
        db.commit()
    except UniqueViolation:
        db.rollback()
        return ({"error": "这个邮箱已经注册过了，请直接登录"}, 409)
    user = repository.find_registered_user(db, (user_id,))
    return ({"user": user_json(user), "_session_version": user.get("session_version", 0)}, 201)


def login(*, data, get_db):
    if not isinstance(data, dict):
        return ({"error": "请提交有效的表单对象"}, 400)
    if any(not isinstance(data.get(key), str) for key in ("email", "password")):
        return ({"error": "请填写邮箱和密码"}, 400)
    email = data["email"].strip().lower()
    password = data["password"]
    if not email or len(email) > 254 or not 1 <= len(password) <= 128:
        return ({"error": "邮箱或密码格式不正确"}, 400)
    user = repository.find_user_by_email(get_db(), (email,))
    if user is None or not check_password_hash(user["password_hash"], password):
        return ({"error": "邮箱或密码不正确，请重试"}, 401)
    return {"user": user_json(user), "_session_version": user.get("session_version", 0)}


def logout():
    return {"message": "已退出登录"}


def delete_account(*, user_id, get_db):
    db = get_db()
    user = repository.find_avatar(db, (user_id,))
    if user is None:
        return ({"error": "账号不存在或已注销"}, 404)
    course_rows = repository.list_account_files(db, (user_id,))
    repository.delete_account_learning(db, (user_id,))
    repository.delete_owned_courses(db, (user_id,))
    repository.delete_user(db, (user_id,))
    db.commit()
    files_to_remove = [
        upload_folder() / row["filename"] for row in course_rows if row["filename"]
    ]
    if user["avatar_filename"]:
        files_to_remove.append(upload_folder() / user["avatar_filename"])
    for stored_file in files_to_remove:
        if stored_file.is_file():
            stored_file.unlink()
    return {"message": "账号已注销"}


def update_profile(*, user_id, form, files, get_db):
    name = str(form.get("name", "")).strip()
    if not name or len(name) > 40:
        return ({"error": "昵称不能为空且不能超过 40 个字符"}, 400)
    db = get_db()
    avatar = files.get("avatar")
    filename = None
    if avatar and avatar.filename:
        if not allowed_file(avatar.filename) and "." not in avatar.filename:
            return ({"error": "头像格式不支持"}, 400)
        extension = avatar.filename.rsplit(".", 1)[-1].lower()
        if extension not in AVATAR_EXTENSIONS:
            return ({"error": "头像仅支持 JPG、PNG、GIF 或 WEBP"}, 400)
        filename = f"{token_hex(12)}.{extension}"
        avatar.save(upload_folder() / filename)
    if filename:
        repository.update_name_and_avatar(db, (name, filename, user_id))
    else:
        repository.update_name(db, (name, user_id))
    db.commit()
    user = repository.find_updated_user(db, (user_id,))
    return {"user": user_json(user)}


def update_password(*, user_id, data, get_db):
    if not isinstance(data, dict):
        return ({"error": "请提交有效的表单对象"}, 400)
    if any(not isinstance(data.get(key), str) for key in ("current_password", "new_password")):
        return ({"error": "请填写当前密码和新密码"}, 400)
    current = data["current_password"]
    if len(current) > 128:
        return ({"error": "当前密码格式不正确"}, 400)
    new_password = str(data.get("new_password", ""))
    user = repository.find_password_hash(get_db(), (user_id,))
    if not user or not check_password_hash(user["password_hash"], current):
        return ({"error": "当前密码不正确"}, 400)
    if not 6 <= len(new_password) <= 128 or not new_password.strip():
        return ({"error": "新密码需要 6–128 位且不能全为空白"}, 400)
    db = get_db()
    updated = repository.update_password_hash(db, (generate_password_hash(new_password), user_id, user["password_hash"]))
    if updated.rowcount != 1:
        db.rollback()
        return ({"error": "密码已被其他请求修改，请重新登录"}, 409)
    db.commit()
    return {"message": "密码修改成功"}
