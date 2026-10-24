"""Learning business rules. HTTP parsing and session changes belong to routes."""

from app.courses.service import course_json
from app.learning import repository
from app.learning.content import MISSION, MODULES
from app.learning.paths import (
    GOALS,
    LEVELS,
    PATHS,
    learning_snapshot,
    learning_status,
    read_profile,
)
from app.learning.study import EXERCISES, notebook
from app.missions import repository as mission_repository
from app.missions.service import public_attempt


def exercise_result(row, exercise):
    return (
        {
            "choice_id": row["choice_id"],
            "correct": row["correct"],
            "attempts": row["attempts"],
            "explanation": exercise["explanations"][row["choice_id"]],
            "correct_choice_id": exercise["correct"],
            "updated_at": row["updated_at"],
        }
        if row
        else None
    )


def course_context(db, user_id, course_id):
    row = repository.find_course_context(db, (user_id, course_id))
    module = next((m for m in MODULES if row and m["slug"] == row["slug"]), None)
    if row and module:
        row = {**row, "title": module["title"]}
    return (row, module)


def learning_courses(*, user_id, get_db):
    rows = repository.list_enrolled_courses(get_db(), (user_id,))
    return {"courses": [course_json(get_db(), row) for row in rows]}


def start_learning(course_id: int, *, user_id, get_db):
    from app.learning.paths import record_visit

    db = get_db()
    if repository.find_course(db, (course_id,)) is None:
        return ({"error": "课程不存在"}, 404)
    repository.upsert_enrollment(db, (user_id, course_id))
    record_visit(db, user_id, course_id)
    db.commit()
    return {"message": "课程已加入学习记录"}


def stop_learning(course_id: int, *, user_id, get_db):
    db = get_db()
    cursor = repository.delete_enrollment(db, (user_id, course_id))
    if cursor.rowcount == 0:
        return ({"error": "该课程不在你的学习列表中"}, 404)
    db.commit()
    return {"message": "已停止学习该课程"}


def learning_profile(*, user_id, get_db):
    return {"profile": read_profile(get_db(), user_id)}


def save_learning_profile(*, user_id, data, get_db):
    if not isinstance(data, dict) or set(data) - {"goal", "level", "weekly_hours"}:
        return ({"error": "请提交学习目标、基础和每周可用时间"}, 400)
    profile = read_profile(get_db(), user_id)
    profile.update(data)
    if not isinstance(profile["goal"], str) or profile["goal"] not in {"", *GOALS}:
        return ({"error": "请选择有效的学习目标"}, 400)
    if not isinstance(profile["level"], str) or profile["level"] not in {"", *LEVELS}:
        return ({"error": "请选择有效的基础水平"}, 400)
    hours = profile["weekly_hours"]
    if hours is not None and (type(hours) is not int or not 1 <= hours <= 40):
        return ({"error": "每周学习时间应为 1–40 小时的整数，也可以留空"}, 400)
    db = get_db()
    repository.upsert_profile(db, (user_id, profile["goal"], profile["level"], hours))
    db.commit()
    return {"profile": read_profile(db, user_id)}


def select_learning_path(*, user_id, data, get_db):
    path_id = data.get("path_id") if isinstance(data, dict) else None
    if not isinstance(path_id, str) or not any((p["id"] == path_id for p in PATHS)):
        return ({"error": "请选择有效的学习路径"}, 400)
    db = get_db()
    selected = next(
        (p for p in learning_snapshot(db, user_id)["catalog"] if p["id"] == path_id)
    )
    if not selected["available"]:
        return ({"error": "该路径的课程暂不完整，请选择其他路径"}, 409)
    repository.upsert_active_path(db, (user_id, path_id))
    db.commit()
    return {"active_path_id": path_id, "message": "已选择学习路径，原学习记录已保留"}


def course_lesson(course_id, *, user_id, get_db):
    row = repository.find_lesson(get_db(), (user_id, course_id))
    if row is None:
        return ({"error": "课程不存在或已下架"}, 404)
    module = next((m for m in MODULES if m["slug"] == row["slug"]), {})
    from app.studio.authoring import read_studio
    studio = read_studio(get_db(), course_id)
    return {
        "lesson": {
            **module,
            **dict(row),
            "studio": studio,
            "title": module.get("title", row["title"]),
            "status": learning_status(row["progress"], row["enrolled"]),
            "file_url": f"/uploads/{row['filename']}" if row["filename"] else None,
        }
    }


def read_exercise(course_id, *, user_id, get_db):
    db = get_db()
    course, module = course_context(db, user_id, course_id)
    if not course:
        return ({"error": "课程不存在或已下架"}, 404)
    exercise = EXERCISES.get(module["slug"]) if module else None
    if not exercise:
        return {"exercise": None, "result": None}
    row = repository.find_exercise_result(db, (user_id, course_id, exercise["version"]))
    return {
        "exercise": {k: exercise[k] for k in ("version", "question", "choices")},
        "result": exercise_result(row, exercise),
    }


def submit_exercise(course_id, *, user_id, data, get_db):
    db = get_db()
    course, module = course_context(db, user_id, course_id)
    if not course:
        return ({"error": "课程不存在或已下架"}, 404)
    exercise = EXERCISES.get(module["slug"]) if module else None
    if not exercise:
        return ({"error": "本课暂未配置固定练习"}, 404)
    if (
        not isinstance(data, dict)
        or data.get("version") != exercise["version"]
        or (not isinstance(data.get("choice_id"), str))
        or (not any((c["id"] == data["choice_id"] for c in exercise["choices"])))
    ):
        return ({"error": "请选择有效选项；题目更新后请重新打开课时"}, 400)
    row = repository.upsert_exercise_result(
        db,
        (
            user_id,
            course_id,
            exercise["version"],
            data["choice_id"],
            data["choice_id"] == exercise["correct"],
        ),
    )
    db.commit()
    return {"result": exercise_result(row, exercise)}


def read_notebook(course_id, *, user_id, get_db):
    if not course_context(get_db(), user_id, course_id)[0]:
        return ({"error": "课程不存在或已下架"}, 404)
    return {"notebook": notebook(get_db(), user_id, course_id)}


def save_notebook(course_id, *, user_id, data, get_db):
    if (
        not isinstance(data, dict)
        or set(data) - {"notes", "task_draft", "revision"}
        or type(data.get("revision")) is not int
        or (data["revision"] < 0)
    ):
        return ({"error": "笔记版本无效，请重新载入后重试"}, 400)
    if not any((key in data for key in ("notes", "task_draft"))) or any(
        (
            key in data and (not isinstance(data[key], str) or len(data[key]) > limit)
            for key, limit in (("notes", 12000), ("task_draft", 4000))
        )
    ):
        return ({"error": "笔记最多 12000 字，任务草稿最多 4000 字"}, 400)
    db = get_db()
    if not course_context(db, user_id, course_id)[0]:
        return ({"error": "课程不存在或已下架"}, 404)
    current = notebook(db, user_id, course_id)
    if current["revision"] != data["revision"]:
        return (
            {"error": "笔记已在其他窗口更新。请先复制本地内容，再重新载入账号版本。"},
            409,
        )
    notes = data.get("notes", current["notes"])
    draft = data.get("task_draft", current["task_draft"])
    row = None
    if data["revision"] == 0:
        row = repository.insert_notebook(db, (user_id, course_id, notes, draft))
    if row is None:
        row = repository.update_notebook_revision(
            db, (notes, draft, user_id, course_id, data["revision"])
        )
    if row is None:
        db.rollback()
        return (
            {"error": "笔记已在其他窗口更新。请先复制本地内容，再重新载入账号版本。"},
            409,
        )
    db.commit()
    return {"notebook": notebook(db, user_id, course_id)}


def path(*, user_id, get_db):
    from app.learning.paths import learning_snapshot

    db = get_db()
    result = learning_snapshot(db, user_id)
    attempts = mission_repository.find_latest_mission(db, (user_id, MISSION["id"]))
    best = mission_repository.find_best_mission_score(
        db, (user_id, MISSION["id"], len(MISSION["steps"]))
    )["score"]
    result["mission"] = {
        "title": MISSION["title"],
        "description": MISSION["description"],
        "best_score": best,
        "attempt": public_attempt(attempts) if attempts else None,
    }
    return result


def progress(course_id, *, user_id, data, get_db):
    value = data.get("progress") if isinstance(data, dict) else None
    if type(value) is not int or not 0 <= value <= 100:
        return ({"error": "进度必须是 0–100 的整数"}, 400)
    db = get_db()
    row = repository.update_enrolled_progress(db, (value, user_id, course_id))
    if row is None:
        return ({"error": "请先加入该课程的学习记录"}, 404)
    db.commit()
    return {"progress": row["progress"]}
