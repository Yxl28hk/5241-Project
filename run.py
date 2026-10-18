from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Mapping

from flask import Flask, g, jsonify, request, send_from_directory, session
import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


from config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ALLOWED_EXTENSIONS,
    AVATAR_EXTENSIONS,
    BASE_DIR,
    DATABASE_URL,
    MAX_FILE_SIZE,
    SECRET_KEY,
    UPLOAD_FOLDER,
)

app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
UPLOAD_FOLDER.mkdir(exist_ok=True)

SEED_COURSES = [
    ("品牌设计的底层逻辑", "设计", "video", "从策略到视觉，建立一套完整的品牌思维", "林默", "6小时 24分", "design", "热门推荐"),
    ("Python 数据分析入门", "技术", "video", "用 Python 掌握数据分析的核心方法与工具", "陈知", "8小时 12分", "tech", "新课上线"),
    ("高效能人士的商业思维", "商业", "pdf", "拆解商业本质，培养你的长期主义决策力", "周远", "4小时 50分", "business", "精选好课"),
    ("如何建立你的知识体系", "人文", "ppt", "从信息收集到输出，打造个人知识管理系统", "苏晴", "3小时 35分", "humanities", "学习方法"),
    ("用户体验设计实战", "设计", "pdf", "用设计思维解决真实世界的产品问题", "叶舟", "5小时 20分", "design", "进阶课程"),
    ("表达力：把话说到心里", "人文", "word", "训练清晰、有感染力的表达与沟通能力", "沈一", "2小时 48分", "humanities", "高口碑"),
]


def get_db() -> Connection[Any]:
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set it to your Neon PostgreSQL connection string."
            )
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def initialize_database() -> None:
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student', 'teacher', 'admin')),
            avatar_filename TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS courses (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL,
            duration TEXT NOT NULL DEFAULT '新资源',
            cover TEXT NOT NULL DEFAULT 'design',
            badge TEXT NOT NULL DEFAULT '我的课程',
            filename TEXT,
            owner_id BIGINT REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS learning_records (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, course_id)
        )"""
    )
    if db.execute("SELECT COUNT(*) AS count FROM courses").fetchone()["count"] == 0:
        for seed in SEED_COURSES:
            db.execute(
                """INSERT INTO courses
                (title, category, resource_type, description, author, duration, cover, badge)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                seed,
            )
    admin = db.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,)).fetchone()
    if admin is None and ADMIN_PASSWORD:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
            ("平台管理员", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)),
        )
    elif admin is not None:
        db.execute("UPDATE users SET role = 'admin' WHERE email = %s", (ADMIN_EMAIL,))
    db.execute("UPDATE users SET role = 'student' WHERE role = 'user'")
    db.commit()


def course_json(row: Mapping[str, Any]) -> dict:
    course = dict(row)
    course["type"] = course.pop("resource_type")
    course["file_url"] = f"/uploads/{course['filename']}" if course["filename"] else None
    course["learner_count"] = get_db().execute(
        "SELECT COUNT(*) AS count FROM learning_records WHERE course_id = %s", (course["id"],)
    ).fetchone()["count"]
    return course


def user_json(row: Mapping[str, Any]) -> dict:
    user = dict(row)
    user.pop("password_hash", None)
    user["avatar_url"] = f"/avatars/{user['avatar_filename']}" if user.get("avatar_filename") else None
    user["is_admin"] = user.get("role") == "admin"
    user.pop("avatar_filename", None)
    user["is_teacher"] = user.get("role") == "teacher"
    user["can_upload"] = user.get("role") in {"teacher", "admin"}
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="请先登录"), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = get_db().execute("SELECT role FROM users WHERE id = %s", (session["user_id"],)).fetchone()
        if not user or user["role"] != "admin":
            return jsonify(error="需要管理员权限"), 403
        return view(*args, **kwargs)

    return wrapped


def teacher_or_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = get_db().execute("SELECT role FROM users WHERE id = %s", (session["user_id"],)).fetchone()
        if not user or user["role"] not in {"teacher", "admin"}:
            return jsonify(error="只有教师或管理员可以上传课程"), 403
        return view(*args, **kwargs)

    return wrapped


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(error="文件不能超过 500MB"), 413


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<filename>")
def static_asset(filename):
    if filename not in {"app.js", "styles.css", "prototype.js", "prototype.css"}:
        return jsonify(error="文件不存在"), 404
    return send_from_directory(BASE_DIR, filename)


@app.get("/api/auth/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(user=None)
    user = get_db().execute("SELECT id, name, email, avatar_filename, role FROM users WHERE id = %s", (user_id,)).fetchone()
    return jsonify(user=user_json(user) if user else None)


@app.get("/api/admin/users")
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        """SELECT id, name, email, role, avatar_filename, created_at
        FROM users ORDER BY created_at DESC, id DESC"""
    ).fetchall()
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
    courses = db.execute(
        """SELECT id, owner_id, title, category, resource_type, description,
        author, duration, cover, badge, filename, created_at
        FROM courses WHERE owner_id IS NOT NULL
        ORDER BY created_at DESC, id DESC"""
    ).fetchall()
    for course in courses:
        user_data[course["owner_id"]]["courses"].append(dict(course))

    learning_records = db.execute(
        """SELECT l.user_id, l.course_id, l.progress, l.started_at, l.updated_at,
        c.title, c.category, c.resource_type, c.author
        FROM learning_records l
        JOIN courses c ON c.id = l.course_id
        ORDER BY l.updated_at DESC"""
    ).fetchall()
    for record in learning_records:
        user_data[record["user_id"]]["learning_records"].append(dict(record))

    return jsonify(users=list(user_data.values()))


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "student")).strip().lower()
    if not name or not email or len(password) < 6:
        return jsonify(error="请填写昵称、有效邮箱和至少 6 位密码"), 400
    if role not in {"student", "teacher"}:
        return jsonify(error="请选择学生或教师角色"), 400
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, email, generate_password_hash(password), role),
        )
        user_id = cursor.fetchone()["id"]
        db.commit()
    except UniqueViolation:
        db.rollback()
        return jsonify(error="这个邮箱已经注册过了，请直接登录"), 409
    session["user_id"] = user_id
    user = db.execute("SELECT id, name, email, role, avatar_filename FROM users WHERE id = %s", (user_id,)).fetchone()
    return jsonify(user=user_json(user)), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = get_db().execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="邮箱或密码不正确，请重试"), 401
    session["user_id"] = user["id"]
    return jsonify(user=user_json(user))


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(message="已退出登录")


@app.delete("/api/profile")
@login_required
def delete_account():
    user_id = session["user_id"]
    db = get_db()
    user = db.execute(
        "SELECT avatar_filename FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    if user is None:
        session.clear()
        return jsonify(error="账号不存在或已注销"), 404

    course_rows = db.execute(
        "SELECT filename FROM courses WHERE owner_id = %s", (user_id,)
    ).fetchall()
    db.execute("DELETE FROM learning_records WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM courses WHERE owner_id = %s", (user_id,))
    db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()

    files_to_remove = [
        UPLOAD_FOLDER / row["filename"]
        for row in course_rows
        if row["filename"]
    ]
    if user["avatar_filename"]:
        files_to_remove.append(UPLOAD_FOLDER / user["avatar_filename"])
    for stored_file in files_to_remove:
        if stored_file.is_file():
            stored_file.unlink()

    session.clear()
    return jsonify(message="账号已注销")


@app.patch("/api/profile")
@login_required
def update_profile():
    name = str(request.form.get("name", "")).strip()
    if not name or len(name) > 40:
        return jsonify(error="昵称不能为空且不能超过 40 个字符"), 400
    db = get_db()
    avatar = request.files.get("avatar")
    filename = None
    if avatar and avatar.filename:
        if not allowed_file(avatar.filename) and "." not in avatar.filename:
            return jsonify(error="头像格式不支持"), 400
        extension = avatar.filename.rsplit(".", 1)[-1].lower()
        if extension not in AVATAR_EXTENSIONS:
            return jsonify(error="头像仅支持 JPG、PNG、GIF 或 WEBP"), 400
        filename = f"{token_hex(12)}.{extension}"
        avatar.save(UPLOAD_FOLDER / filename)
    if filename:
        db.execute("UPDATE users SET name = %s, avatar_filename = %s WHERE id = %s", (name, filename, session["user_id"]))
    else:
        db.execute("UPDATE users SET name = %s WHERE id = %s", (name, session["user_id"]))
    db.commit()
    user = db.execute("SELECT id, name, email, role, avatar_filename FROM users WHERE id = %s", (session["user_id"],)).fetchone()
    return jsonify(user=user_json(user))


@app.patch("/api/profile/password")
@login_required
def update_password():
    data = request.get_json(silent=True) or {}
    current = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    user = get_db().execute("SELECT password_hash FROM users WHERE id = %s", (session["user_id"],)).fetchone()
    if not user or not check_password_hash(user["password_hash"], current):
        return jsonify(error="当前密码不正确"), 400
    if len(new_password) < 6:
        return jsonify(error="新密码至少需要 6 位"), 400
    db = get_db()
    db.execute("UPDATE users SET password_hash = %s WHERE id = %s", (generate_password_hash(new_password), session["user_id"]))
    db.commit()
    return jsonify(message="密码修改成功")


@app.get("/api/courses")
def courses():
    query = str(request.args.get("q", "")).strip()
    category = str(request.args.get("category", "全部")).strip()
    conditions, params = [], []
    if query:
        conditions.append("(title LIKE %s OR description LIKE %s OR author LIKE %s)")
        params.extend([f"%{query}%"] * 3)
    if category and category != "全部":
        conditions.append("category = %s")
        params.append(category)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = get_db().execute(f"SELECT * FROM courses {where} ORDER BY created_at DESC, id DESC", params).fetchall()
    return jsonify(courses=[course_json(row) for row in rows])


@app.post("/api/courses")
@teacher_or_admin_required
def create_course():
    title = str(request.form.get("title", "")).strip()
    category = str(request.form.get("category", "")).strip()
    resource_type = str(request.form.get("type", "")).strip().lower()
    description = str(request.form.get("description", "")).strip()
    file = request.files.get("file")
    if not title or category not in {"设计", "技术", "商业", "人文"}:
        return jsonify(error="请填写课程名称并选择有效分类"), 400
    if file is None or not file.filename or not allowed_file(file.filename):
        return jsonify(error="请选择 PDF、Word、PPT 或视频文件"), 400
    if resource_type not in {"pdf", "word", "ppt", "video"}:
        return jsonify(error="不支持的资源类型"), 400
    user = get_db().execute("SELECT name FROM users WHERE id = %s", (session["user_id"],)).fetchone()
    safe_name = secure_filename(file.filename)
    stored_name = f"{token_hex(12)}_{safe_name}"
    file.save(UPLOAD_FOLDER / stored_name)
    cover = {"pdf": "business", "video": "tech", "ppt": "humanities", "word": "design"}[resource_type]
    db = get_db()
    cursor = db.execute(
        """INSERT INTO courses
        (title, category, resource_type, description, author, duration, cover, badge, filename, owner_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id""",
        (title, category, resource_type, description or f"包含 {file.filename} 的学习资料", user["name"], "新资源", cover, "刚刚上传", stored_name, session["user_id"]),
    )
    course_id = cursor.fetchone()["id"]
    db.commit()
    row = db.execute("SELECT * FROM courses WHERE id = %s", (course_id,)).fetchone()
    return jsonify(course=course_json(row)), 201


@app.get("/api/profile/courses")
@teacher_or_admin_required
def my_courses():
    db = get_db()
    current_user = db.execute(
        "SELECT role FROM users WHERE id = %s", (session["user_id"],)
    ).fetchone()
    if current_user and current_user["role"] == "admin":
        rows = db.execute(
            "SELECT * FROM courses ORDER BY created_at DESC, id DESC"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM courses WHERE owner_id = %s ORDER BY created_at DESC, id DESC",
            (session["user_id"],),
        ).fetchall()
    return jsonify(courses=[course_json(row) for row in rows])


@app.get("/api/profile/learning")
@login_required
def learning_courses():
    rows = get_db().execute(
        """SELECT c.*, l.progress FROM learning_records l
        JOIN courses c ON c.id = l.course_id
        WHERE l.user_id = %s ORDER BY l.updated_at DESC""",
        (session["user_id"],),
    ).fetchall()
    return jsonify(courses=[course_json(row) for row in rows])


def managed_course(course_id: int) -> Mapping[str, Any] | None:
    db = get_db()
    user = db.execute("SELECT role FROM users WHERE id = %s", (session["user_id"],)).fetchone()
    if user and user["role"] == "admin":
        return db.execute("SELECT * FROM courses WHERE id = %s", (course_id,)).fetchone()
    return db.execute(
        "SELECT * FROM courses WHERE id = %s AND owner_id = %s",
        (course_id, session["user_id"]),
    ).fetchone()


@app.get("/api/courses/<int:course_id>/learners")
@teacher_or_admin_required
def course_learners(course_id: int):
    if managed_course(course_id) is None:
        return jsonify(error="没有权限查看该课程的学习人员"), 404
    rows = get_db().execute(
        """SELECT u.id, u.name, l.progress, l.updated_at
        FROM learning_records l JOIN users u ON u.id = l.user_id
        WHERE l.course_id = %s ORDER BY l.updated_at DESC""",
        (course_id,),
    ).fetchall()
    return jsonify(learners=[dict(row) for row in rows])


@app.delete("/api/courses/<int:course_id>/learners/<int:user_id>")
@teacher_or_admin_required
def remove_course_learner(course_id: int, user_id: int):
    if managed_course(course_id) is None:
        return jsonify(error="没有权限管理该课程的学习人员"), 404
    cursor = get_db().execute(
        "DELETE FROM learning_records WHERE course_id = %s AND user_id = %s",
        (course_id, user_id),
    )
    if cursor.rowcount == 0:
        return jsonify(error="该用户不在课程学习名单中"), 404
    get_db().commit()
    return jsonify(message="已移除该学习人员")


@app.post("/api/courses/<int:course_id>/learn")
@login_required
def start_learning(course_id: int):
    db = get_db()
    if db.execute("SELECT id FROM courses WHERE id = %s", (course_id,)).fetchone() is None:
        return jsonify(error="课程不存在"), 404
    db.execute(
        """INSERT INTO learning_records (user_id, course_id) VALUES (%s, %s)
        ON CONFLICT(user_id, course_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP""",
        (session["user_id"], course_id),
    )
    db.commit()
    return jsonify(message="课程已加入学习记录")


@app.delete("/api/profile/learning/<int:course_id>")
@login_required
def stop_learning(course_id: int):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM learning_records WHERE user_id = %s AND course_id = %s",
        (session["user_id"], course_id),
    )
    if cursor.rowcount == 0:
        return jsonify(error="该课程不在你的学习列表中"), 404
    db.commit()
    return jsonify(message="已停止学习该课程")


@app.delete("/api/courses/<int:course_id>")
@teacher_or_admin_required
def delete_course(course_id: int):
    db = get_db()
    current_user = db.execute("SELECT role FROM users WHERE id = %s", (session["user_id"],)).fetchone()
    if current_user and current_user["role"] == "admin":
        course = db.execute("SELECT filename FROM courses WHERE id = %s", (course_id,)).fetchone()
    else:
        course = db.execute(
            "SELECT filename FROM courses WHERE id = %s AND owner_id = %s",
            (course_id, session["user_id"]),
        ).fetchone()
    if course is None:
        return jsonify(error="没有权限删除该课程，或课程不存在"), 404
    db.execute("DELETE FROM learning_records WHERE course_id = %s", (course_id,))
    if current_user and current_user["role"] == "admin":
        db.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    else:
        db.execute("DELETE FROM courses WHERE id = %s AND owner_id = %s", (course_id, session["user_id"]))
    db.commit()
    if course["filename"]:
        stored_file = UPLOAD_FOLDER / course["filename"]
        if stored_file.is_file():
            stored_file.unlink()
    return jsonify(message="课程已删除")


@app.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.get("/avatars/<path:filename>")
def avatar_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


from app.routes.prototype import register_prototype, initialize_prototype
register_prototype(app, get_db, login_required)


@app.cli.command("init-db")
def init_db_command():
    """Create additive schema and seed classroom learning content."""
    initialize_database()
    initialize_prototype(get_db())
    print("Database initialized.")


if __name__ == "__main__":
    with app.app_context():
        initialize_database()
        initialize_prototype(get_db())
    app.run(host="127.0.0.1", port=int(__import__("os").environ.get("PORT", "5000")), debug=False)
