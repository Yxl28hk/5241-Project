"""Personal profile, explicit path selection and readable lesson endpoints."""

from flask import jsonify, request, session

from app.models.content import MODULES
from app.models.learner import GOALS, LEVELS, PATHS, learning_snapshot, learning_status, read_profile


def register_learning(app, get_db, login_required):
    @app.get("/api/learning-profile")
    @login_required
    def learning_profile():
        return jsonify(profile=read_profile(get_db(), session["user_id"]))

    @app.patch("/api/learning-profile")
    @login_required
    def save_learning_profile():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - {"goal", "level", "weekly_hours"}:
            return jsonify(error="请提交学习目标、基础和每周可用时间"), 400
        profile = read_profile(get_db(), session["user_id"])
        profile.update(data)
        if not isinstance(profile["goal"], str) or profile["goal"] not in {"", *GOALS}:
            return jsonify(error="请选择有效的学习目标"), 400
        if not isinstance(profile["level"], str) or profile["level"] not in {"", *LEVELS}:
            return jsonify(error="请选择有效的基础水平"), 400
        hours = profile["weekly_hours"]
        if hours is not None and (type(hours) is not int or not 1 <= hours <= 40):
            return jsonify(error="每周学习时间应为 1–40 小时的整数，也可以留空"), 400
        db = get_db()
        db.execute("""INSERT INTO learning_profiles (user_id, goal, level, weekly_hours) VALUES (%s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET goal = EXCLUDED.goal, level = EXCLUDED.level,
            weekly_hours = EXCLUDED.weekly_hours, updated_at = CURRENT_TIMESTAMP""",
                   (session["user_id"], profile["goal"], profile["level"], hours))
        db.commit()
        return jsonify(profile=read_profile(db, session["user_id"]))

    @app.post("/api/learning-path/select")
    @login_required
    def select_learning_path():
        data = request.get_json(silent=True)
        path_id = data.get("path_id") if isinstance(data, dict) else None
        if not isinstance(path_id, str) or not any(p["id"] == path_id for p in PATHS):
            return jsonify(error="请选择有效的学习路径"), 400
        db = get_db()
        selected = next(p for p in learning_snapshot(db, session["user_id"])["catalog"] if p["id"] == path_id)
        if not selected["available"]:
            return jsonify(error="该路径的课程暂不完整，请选择其他路径"), 409
        db.execute("""INSERT INTO learner_preferences (user_id, active_path_slug) VALUES (%s, %s)
            ON CONFLICT(user_id) DO UPDATE SET active_path_slug = EXCLUDED.active_path_slug""",
                   (session["user_id"], path_id))
        db.commit()
        return jsonify(active_path_id=path_id, message="已选择学习路径，原学习记录已保留")

    @app.get("/api/courses/<int:course_id>/lesson")
    @login_required
    def course_lesson(course_id):
        row = get_db().execute("""SELECT c.id, c.title, c.description, c.filename, c.duration, p.slug,
            COALESCE(l.progress, 0) AS progress, (l.user_id IS NOT NULL) AS enrolled, l.last_opened_at FROM courses c
            LEFT JOIN prototype_courses p ON p.course_id = c.id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s WHERE c.id = %s""",
                               (session["user_id"], course_id)).fetchone()
        if row is None:
            return jsonify(error="课程不存在或已下架"), 404
        module = next((m for m in MODULES if m["slug"] == row["slug"]), {})
        return jsonify(lesson={**module, **dict(row), "title":module.get("title",row["title"]), "status": learning_status(row["progress"], row["enrolled"]),
                               "file_url": f"/uploads/{row['filename']}" if row["filename"] else None})
