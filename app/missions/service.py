"""Missions business rules. HTTP parsing and session changes belong to routes."""

import json

from app.learning.content import MISSION
from app.missions import repository


def public_attempt(row):
    step = row["step"]
    result = {
        "id": row["id"],
        "step": step,
        "score": row["score"],
        "complete": step == len(MISSION["steps"]),
        "total": len(MISSION["steps"]),
        "history": json.loads(row["answers"]),
    }
    if result["complete"]:
        result["passed"] = row["score"] >= 75
    else:
        current = MISSION["steps"][step]
        result["current"] = {
            "title": current["title"],
            "scenario": current["scenario"],
            "choices": [{"id": c["id"], "text": c["text"]} for c in current["choices"]],
        }
    return result


def start(*, user_id, get_db):
    db = get_db()
    existing = repository.find_unfinished_attempt(
        db, (user_id, MISSION["id"], len(MISSION["steps"]))
    )
    if existing:
        return {"attempt": public_attempt(existing)}
    row = repository.insert_attempt(db, (user_id, MISSION["id"]))
    db.commit()
    return ({"attempt": public_attempt(row)}, 201)


def answer(attempt_id, *, user_id, data, get_db):
    db = get_db()
    row = repository.find_owned_attempt(db, (attempt_id, user_id))
    if row is None:
        return ({"error": "任务记录不存在"}, 404)
    if not isinstance(data, dict) or type(data.get("step")) is not int:
        return ({"error": "请选择当前场景的选项"}, 400)
    if row["step"] == len(MISSION["steps"]) or data["step"] != row["step"]:
        return ({"error": "步骤已更新，请重新打开任务"}, 409)
    current = MISSION["steps"][row["step"]]
    choice = next(
        (c for c in current["choices"] if c["id"] == data.get("choice_id")), None
    )
    if choice is None:
        return ({"error": "选项无效"}, 400)
    history = json.loads(row["answers"]) + [{"title": current["title"], **choice}]
    updated = repository.advance_attempt(
        db,
        (
            choice["points"],
            json.dumps(history, ensure_ascii=False),
            attempt_id,
            user_id,
            row["step"],
        ),
    )
    if updated is None:
        db.rollback()
        return ({"error": "该选择已经提交，请重新打开任务"}, 409)
    db.commit()
    return {"attempt": public_attempt(updated), "feedback": choice["feedback"]}
