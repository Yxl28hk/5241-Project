"""Compatibility adapter for the learning-path route module.

The implementation now lives under ``app.routes``; this module remains so
existing imports and deployments continue to work.
"""

from app.models.content import MODULES, MISSION

import json
from flask import jsonify, request, session
from app.models.tutor import tutor_mode, validate_history


def initialize_prototype(db):
    from app.models.learner import initialize_learning
    initialize_learning(db)
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
        return jsonify(database="postgresql", tutor_mode=tutor_mode(app))

    @app.get("/api/learning-path")
    @login_required
    def path():
        from app.models.learner import learning_snapshot
        db = get_db()
        result = learning_snapshot(db, session["user_id"])
        attempts = db.execute("""SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            ORDER BY id DESC LIMIT 1""", (session["user_id"], MISSION["id"])).fetchone()
        best = db.execute("""SELECT MAX(score) AS score FROM mission_attempts
            WHERE user_id = %s AND mission_id = %s AND step = %s""",
            (session["user_id"], MISSION["id"], len(MISSION["steps"]))).fetchone()["score"]
        result["mission"] = {"title": MISSION["title"], "description": MISSION["description"],
                             "best_score": best, "attempt": public_attempt(attempts) if attempts else None}
        return jsonify(result)

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
        history = data.get("history", [])
        requested_mode = data.get("mode", "auto")
        if not validate_history(history) or not isinstance(requested_mode, str) or requested_mode not in {"auto", "guided-demo"}:
            return jsonify(error="会话格式无效，请清空对话后重试"), 400
        row = get_db().execute("""SELECT c.id, c.title, c.description, p.slug, COALESCE(l.progress, 0) AS progress
            FROM courses c LEFT JOIN prototype_courses p ON p.course_id = c.id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s WHERE c.id = %s""",
            (session["user_id"], course_id)).fetchone()
        if row is None:
            return jsonify(error="课程不存在"), 404
        module = next((m for m in MODULES if m["slug"] == row["slug"]), None)
        from app.routes.study import tutor_reply
        return tutor_reply(app,get_db,data,{**row,"title":module["title"] if module else row["title"]},module,session["user_id"])

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
