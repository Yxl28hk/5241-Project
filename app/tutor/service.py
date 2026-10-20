"""Tutor business rules. HTTP parsing and session changes belong to routes."""

import hashlib
import json
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.infrastructure.tutor_provider import (
    TutorUnavailable,
    guided_answer,
    model_answer,
    tutor_mode,
    validate_history,
)
from app.learning.content import MODULES
from app.learning.paths import read_profile
from app.learning.service import course_context
from app.learning.study import EXERCISES, focus_context
from app.tutor import repository
from app.tutor.conversations import open_conversation, public_conversation


def tutor_reply(app, get_db, data, course, module, user_id):
    db = get_db()
    key = data.get("context_key", "overview")
    action = data.get("action", "answer")
    if (
        not isinstance(key, str)
        or len(key) > 40
        or (not isinstance(action, str))
        or (action not in {"answer", "hint", "reference"})
    ):
        return ({"error": "提问范围或操作无效"}, 400)
    focus = focus_context(module, course, key)
    if not focus:
        return ({"error": "所选段落不存在，请重新选择"}, 400)
    if action in {"hint", "reference"} and (
        not module or key not in {"task", "exercise"}
    ):
        return ({"error": "请先选择本节任务或练习"}, 400)
    if action == "hint" and (
        type(data.get("hint_step")) is not int or data["hint_step"] not in {1, 2}
    ):
        return ({"error": "提示分为第 1 步和第 2 步"}, 400)
    persisted = "token" in data
    history = data.get("history", [])
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                k: data.get(k)
                for k in ("message", "context_key", "action", "hint_step", "mode")
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    conversation = None
    if persisted:
        if (
            not isinstance(data["token"], str)
            or type(data.get("revision")) is not int
            or data["revision"] < 0
        ):
            return ({"error": "请先恢复课时会话"}, 400)
        try:
            request_id = str(UUID(data.get("request_id", "")))
        except (ValueError, TypeError, AttributeError):
            return ({"error": "请求标识无效，请重试"}, 400)
        conversation = repository.find_token_conversation(
            db, (user_id, course["id"], data["token"])
        )
        if not conversation:
            return ({"error": "会话已重置，请恢复最新会话后再提问"}, 409)
        if conversation["last_request_id"] == request_id:
            if conversation["last_fingerprint"] != fingerprint:
                return ({"error": "同一请求标识不能用于不同问题"}, 409)
            return {
                **conversation["last_reply"],
                "conversation": public_conversation(conversation),
            }
        if conversation["revision"] != data["revision"]:
            return ({"error": "会话已在其他窗口更新，请恢复最新会话"}, 409)
        history = [
            {"role": m["role"], "content": m["content"][:3000]}
            for m in conversation["messages"][-10:]
        ]
    profile = read_profile(db, user_id)
    db.commit()
    mode = "guided-demo" if data.get("mode") == "guided-demo" else tutor_mode(app)
    if action == "hint":
        group = "quiz_hints" if key == "exercise" else "task_hints"
        answer = (
            f"第 {data['hint_step']} 步提示："
            + EXERCISES[module["slug"]][group][data["hint_step"] - 1]
        )
        mode = "guided-demo"
        label = "预设分步提示"
    elif action == "reference":
        answer = (
            EXERCISES[module["slug"]]["explanations"][
                EXERCISES[module["slug"]]["correct"]
            ]
            if key == "exercise"
            else module["guide"]["task"]["reference"]
        )
        mode = "guided-demo"
        label = "参考解析"
    else:
        if mode == "live":
            try:
                answer = model_answer(
                    app,
                    module,
                    {**course, "focus": focus},
                    data["message"].strip(),
                    history,
                    profile,
                )
            except TutorUnavailable as error:
                return ({"error": str(error), "retryable": True}, 502)
        elif key == "overview":
            answer = guided_answer(module, course, data["message"].strip(), history)
        else:
            answer = (
                "当前选段："
                + focus["title"]
                + "\n\n"
                + focus["text"]
                + "\n\n思考提示："
                + module["hint"]
                + "\n\n这是针对所选内容的预设知识卡。"
            )
        label = (
            "AI 学习助手" if mode == "live" else "课时知识卡 · 规则式助手（非大模型）"
        )
    result = {
        "mode": mode,
        "label": label,
        "answer": answer,
        "context": {
            "title": course["title"],
            "progress": course["progress"],
            "key": key,
            "focus_title": focus["title"],
        },
    }
    if persisted:
        messages = [
            *conversation["messages"],
            {"role": "user", "content": data["message"].strip(), "context_key": key},
            {
                "role": "assistant",
                "content": answer,
                "label": label,
                "mode": mode,
                "context_key": key,
                "action": action,
                "hint_step": data.get("hint_step"),
                "focus_title": focus["title"],
            },
        ][-40:]
        row = repository.save_conversation_revision(
            db,
            (
                Jsonb(messages),
                request_id,
                fingerprint,
                Jsonb(result),
                user_id,
                course["id"],
                data["token"],
                data["revision"],
            ),
        )
        if not row:
            db.rollback()
            return ({"error": "会话已更新或重置，本次回答未写入，请恢复最新会话"}, 409)
        db.commit()
        result["conversation"] = public_conversation(row)
    return result


def restore_conversation(course_id, *, user_id, get_db):
    db = get_db()
    if not course_context(db, user_id, course_id)[0]:
        return ({"error": "课程不存在或已下架"}, 404)
    row = open_conversation(db, user_id, course_id)
    db.commit()
    return {"conversation": public_conversation(row)}


def new_conversation(course_id, *, user_id, data, get_db):
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("token"), str)
        or type(data.get("revision")) is not int
    ):
        return ({"error": "会话版本无效，请恢复会话后重试"}, 400)
    db = get_db()
    row = repository.reset_conversation_revision(
        db, (uuid4().hex, user_id, course_id, data["token"], data["revision"])
    )
    if not row:
        db.rollback()
        return ({"error": "会话已改变，请先恢复最新会话"}, 409)
    db.commit()
    return {"conversation": public_conversation(row)}


def config(*, app):
    return {"database": "postgresql", "tutor_mode": tutor_mode(app)}


def tutor(*, user_id, data, get_db, app):
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("message"), str)
        or (not 1 <= len(data["message"].strip()) <= 1000)
    ):
        return ({"error": "请输入 1–1000 字的问题"}, 400)
    course_id = data.get("course_id")
    if type(course_id) is not int:
        return ({"error": "请选择课程"}, 400)
    history = data.get("history", [])
    requested_mode = data.get("mode", "auto")
    if (
        not validate_history(history)
        or not isinstance(requested_mode, str)
        or requested_mode not in {"auto", "guided-demo"}
    ):
        return ({"error": "会话格式无效，请清空对话后重试"}, 400)
    row = repository.find_course_context(get_db(), (user_id, course_id))
    if row is None:
        return ({"error": "课程不存在"}, 404)
    module = next((m for m in MODULES if m["slug"] == row["slug"]), None)
    return tutor_reply(
        app,
        get_db,
        data,
        {**row, "title": module["title"] if module else row["title"]},
        module,
        user_id,
    )
