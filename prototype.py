"""Additive Week 8 routes. Scores and progress are persisted per signed-in user."""
import json
from flask import jsonify, request, session
from learning_content import MODULES, MISSION


def initialize_prototype(db):
    db.execute("""CREATE TABLE IF NOT EXISTS prototype_courses (
        slug TEXT PRIMARY KEY, course_id BIGINT NOT NULL UNIQUE
        REFERENCES courses(id) ON DELETE CASCADE)""")
    db.execute("""CREATE TABLE IF NOT EXISTS mission_attempts (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        mission_id TEXT NOT NULL, step INTEGER NOT NULL DEFAULT 0,
        score INTEGER NOT NULL DEFAULT 0, answers TEXT NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    for module in MODULES:
        if db.execute("SELECT slug FROM prototype_courses WHERE slug = %s", (module["slug"],)).fetchone():
            continue
        row = db.execute("""INSERT INTO courses
            (title, category, resource_type, description, author, duration, cover, badge)
            VALUES (%s, '技术', 'lesson', %s, '知行软件工程实验室', %s, 'tech', 'Week 8') RETURNING id""",
            (module["title"], module["description"], module["duration"])).fetchone()
        db.execute("INSERT INTO prototype_courses (slug, course_id) VALUES (%s, %s)",
                   (module["slug"], row["id"]))
    db.commit()


def public_attempt(row):
    step = row["step"]
    result = {"id": row["id"], "step": step, "score": row["score"],
              "complete": step == len(MISSION["steps"]), "total": len(MISSION["steps"]),
              "history": json.loads(row["answers"])}
    if result["complete"]:
        result["passed"] = row["score"] >= 75
    else:
        current = MISSION["steps"][step]
        result["current"] = {"title": current["title"], "scenario": current["scenario"],
                             "choices": [{"id": c["id"], "text": c["text"]} for c in current["choices"]]}
    return result


def register_prototype(app, get_db, login_required):
    @app.get("/api/prototype/config")
    def config():
        return jsonify(database="postgresql", tutor_mode="guided-demo")

    @app.get("/api/learning-path")
    @login_required
    def path():
        db = get_db()
        rows = db.execute("""SELECT p.slug, c.id, c.title, COALESCE(l.progress, 0) AS progress
            FROM prototype_courses p JOIN courses c ON c.id = p.course_id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s""",
            (session["user_id"],)).fetchall()
        by_slug = {r["slug"]: dict(r) for r in rows}
        modules = [{**m, **by_slug[m["slug"]]} for m in MODULES if m["slug"] in by_slug]
        attempts = db.execute("""SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            ORDER BY id DESC LIMIT 1""", (session["user_id"], MISSION["id"])).fetchone()
        best = db.execute("""SELECT MAX(score) AS score FROM mission_attempts
            WHERE user_id = %s AND mission_id = %s AND step = %s""",
            (session["user_id"], MISSION["id"], len(MISSION["steps"]))).fetchone()["score"]
        return jsonify(modules=modules, progress=round(sum(m["progress"] for m in modules) / len(modules)) if modules else 0,
                       completed=sum(m["progress"] == 100 for m in modules),
                       next_course_id=next((m["id"] for m in modules if m["progress"] < 100), None),
                       mission={"title": MISSION["title"], "description": MISSION["description"],
                                "best_score": best, "attempt": public_attempt(attempts) if attempts else None})

    @app.patch("/api/courses/<int:course_id>/progress")
    @login_required
    def progress(course_id):
        data = request.get_json(silent=True)
        value = data.get("progress") if isinstance(data, dict) else None
        if type(value) is not int or not 0 <= value <= 100:
            return jsonify(error="进度必须是 0–100 的整数"), 400
        db = get_db()
        row = db.execute("""UPDATE learning_records SET progress = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND course_id = %s RETURNING progress""",
            (value, session["user_id"], course_id)).fetchone()
        if row is None:
            return jsonify(error="请先加入该课程的学习记录"), 404
        db.commit()
        return jsonify(progress=row["progress"])

    @app.post("/api/tutor")
    @login_required
    def tutor():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("message"), str) or not 1 <= len(data["message"].strip()) <= 1000:
            return jsonify(error="请输入 1–1000 字的问题"), 400
        course_id = data.get("course_id")
        if type(course_id) is not int:
            return jsonify(error="请选择课程"), 400
        row = get_db().execute("""SELECT c.title, c.description, p.slug, COALESCE(l.progress, 0) AS progress
            FROM courses c LEFT JOIN prototype_courses p ON p.course_id = c.id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s WHERE c.id = %s""",
            (session["user_id"], course_id)).fetchone()
        if row is None:
            return jsonify(error="课程不存在"), 404
        module = next((m for m in MODULES if m["slug"] == row["slug"]), None)
        question = data["message"].strip().lower()
        if module:
            if any(k in question for k in ["下一步", "next", "计划"]):
                answer = "建议下一步：" + ("尝试 Release Rescue，把知识用于实际决策。" if row["progress"] == 100 else "阅读本节内容，再用自己的话回答检查问题；理解后标记完成。")
            elif any(k in question for k in ["提示", "hint", "不懂"]):
                answer = module["hint"] + "\n检查问题：" + module["question"]
            else:
                answer = "本课知识卡：" + module["lesson"] + "\n试着回答：" + module["question"]
        else:
            answer = "这门课程的简介是：" + row["description"] + "\n演示助手尚未读取上传文件。请先浏览资源，列出一个关键概念和一个疑问，再向教师求证。"
        return jsonify(mode="guided-demo", label="演示模式 · 规则式学习助手（非大模型）", answer=answer,
                       context={"title": row["title"], "progress": row["progress"]})

    @app.post("/api/missions/release-rescue/start")
    @login_required
    def start():
        db = get_db()
        existing = db.execute("""SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            AND step < %s ORDER BY id DESC LIMIT 1""",
            (session["user_id"], MISSION["id"], len(MISSION["steps"]))).fetchone()
        if existing:
            return jsonify(attempt=public_attempt(existing))
        row = db.execute("""INSERT INTO mission_attempts (user_id, mission_id) VALUES (%s, %s) RETURNING *""",
                         (session["user_id"], MISSION["id"])).fetchone()
        db.commit()
        return jsonify(attempt=public_attempt(row)), 201

    @app.post("/api/missions/attempts/<int:attempt_id>/answer")
    @login_required
    def answer(attempt_id):
        db = get_db()
        row = db.execute("SELECT * FROM mission_attempts WHERE id = %s AND user_id = %s",
                         (attempt_id, session["user_id"])).fetchone()
        if row is None:
            return jsonify(error="任务记录不存在"), 404
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("step")) is not int:
            return jsonify(error="请选择当前场景的选项"), 400
        if row["step"] == len(MISSION["steps"]) or data["step"] != row["step"]:
            return jsonify(error="步骤已更新，请重新打开任务"), 409
        current = MISSION["steps"][row["step"]]
        choice = next((c for c in current["choices"] if c["id"] == data.get("choice_id")), None)
        if choice is None:
            return jsonify(error="选项无效"), 400
        history = json.loads(row["answers"]) + [{"title": current["title"], **choice}]
        updated = db.execute("""UPDATE mission_attempts SET step = step + 1, score = score + %s, answers = %s
            WHERE id = %s AND user_id = %s AND step = %s RETURNING *""",
            (choice["points"], json.dumps(history, ensure_ascii=False), attempt_id, session["user_id"], row["step"])).fetchone()
        if updated is None:
            db.rollback()
            return jsonify(error="该选择已经提交，请重新打开任务"), 409
        db.commit()
        return jsonify(attempt=public_attempt(updated), feedback=choice["feedback"])
