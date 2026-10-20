"""Explicit classroom content/account seeding; never runs on import."""

from werkzeug.security import generate_password_hash

from app.learning.content import MODULES

SEED_COURSES = [
    (
        "品牌设计的底层逻辑",
        "设计",
        "video",
        "从策略到视觉，建立一套完整的品牌思维",
        "林默",
        "6小时 24分",
        "design",
        "热门推荐",
    ),
    (
        "Python 数据分析入门",
        "技术",
        "video",
        "用 Python 掌握数据分析的核心方法与工具",
        "陈知",
        "8小时 12分",
        "tech",
        "新课上线",
    ),
    (
        "高效能人士的商业思维",
        "商业",
        "pdf",
        "拆解商业本质，培养你的长期主义决策力",
        "周远",
        "4小时 50分",
        "business",
        "精选好课",
    ),
    (
        "如何建立你的知识体系",
        "人文",
        "ppt",
        "从信息收集到输出，打造个人知识管理系统",
        "苏晴",
        "3小时 35分",
        "humanities",
        "学习方法",
    ),
    (
        "用户体验设计实战",
        "设计",
        "pdf",
        "用设计思维解决真实世界的产品问题",
        "叶舟",
        "5小时 20分",
        "design",
        "进阶课程",
    ),
    (
        "表达力：把话说到心里",
        "人文",
        "word",
        "训练清晰、有感染力的表达与沟通能力",
        "沈一",
        "2小时 48分",
        "humanities",
        "高口碑",
    ),
]


def seed_core(db, admin_email, admin_password) -> None:
    if db.execute("SELECT COUNT(*) AS count FROM courses").fetchone()["count"] == 0:
        for seed in SEED_COURSES:
            db.execute(
                """INSERT INTO courses
                (title, category, resource_type, description, author, duration, cover, badge)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                seed,
            )
    admin = db.execute(
        "SELECT id FROM users WHERE email = %s", (admin_email,)
    ).fetchone()
    if admin is None and admin_password:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
            ("平台管理员", admin_email, generate_password_hash(admin_password)),
        )
    elif admin is not None:
        db.execute("UPDATE users SET role = 'admin' WHERE email = %s", (admin_email,))
    db.execute("UPDATE users SET role = 'student' WHERE role = 'user'")
    db.commit()


def seed_lessons(db):
    for module in MODULES:
        if db.execute(
            "SELECT slug FROM prototype_courses WHERE slug = %s", (module["slug"],)
        ).fetchone():
            continue
        row = db.execute(
            """INSERT INTO courses
            (title, category, resource_type, description, author, duration, cover, badge)
            VALUES (%s, '技术', 'lesson', %s, '知行软件工程实验室', %s, 'tech', 'Week 8') RETURNING id""",
            (module["title"], module["description"], module["duration"]),
        ).fetchone()
        db.execute(
            "INSERT INTO prototype_courses (slug, course_id) VALUES (%s, %s)",
            (module["slug"], row["id"]),
        )
    db.commit()
