"""Auth business rules. HTTP parsing and session changes belong to routes."""

from secrets import token_hex

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
    data = data or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "student")).strip().lower()
    if not name or not email or len(password) < 6:
        return ({"error": "请填写昵称、有效邮箱和至少 6 位密码"}, 400)
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
    return ({"user": user_json(user)}, 201)


def login(*, data, get_db):
    data = data or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = repository.find_user_by_email(get_db(), (email,))
    if user is None or not check_password_hash(user["password_hash"], password):
        return ({"error": "邮箱或密码不正确，请重试"}, 401)
    return {"user": user_json(user)}


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
    data = data or {}
    current = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    user = repository.find_password_hash(get_db(), (user_id,))
    if not user or not check_password_hash(user["password_hash"], current):
        return ({"error": "当前密码不正确"}, 400)
    if len(new_password) < 6:
        return ({"error": "新密码至少需要 6 位"}, 400)
    db = get_db()
    repository.update_password_hash(db, (generate_password_hash(new_password), user_id))
    db.commit()
    return {"message": "密码修改成功"}
