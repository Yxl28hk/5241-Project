"""Quiz business rules. HTTP parsing and session changes belong to routes.

Answers are scored server side; client supplied scores or correctness are ignored.
Quiz results are written to dedicated reference columns and never overwrite the
level a student reported for themselves.

Playability extras (random draw, multi/order questions, boss, hearts, quick and
revenge modes) only affect *which* questions appear and *how* they are rendered.
They never change the scoring chain: correct -> +1 -> best_score -> badge -> reference.
"""

import json
import random
import re
from collections import Counter
from math import ceil

from psycopg import errors
from psycopg.types.json import Jsonb

from app.quiz import repository
from app.quiz.content import (
    ANCHOR_DESCRIPTION,
    ANCHOR_DURATION,
    DRAW_QUOTA,
    HEARTS_PER_LEVEL,
    HEART_LEVEL,
    LEGACY_CODES,
    LEVEL_COUNT,
    LEVELS_META,
    MISSION_ID,
    MISSION_IDS,
    MODE_TOTAL,
    QUESTIONS_PER_LEVEL,
    QUEST_DESCRIPTION,
    QUEST_SUBTITLE,
    QUEST_TITLE,
    QUICK_QUOTA,
    REVENGE_MAX,
    TOPICS,
    TOPIC_LABELS,
    TOTAL_QUESTIONS,
    UNLOCK_RATIO,
    badge_for,
    persona_for,
    judge,
    suggested_level,
    valid_choice,
)

UNLOCK_TARGET = ceil(QUESTIONS_PER_LEVEL * UNLOCK_RATIO)
MODE_BY_MISSION = {value: key for key, value in MISSION_IDS.items()}
ALL_MISSION_IDS = tuple(MISSION_IDS.values())


def _load_pool(db):
    """Every active question; None when the quiz schema is not installed yet."""
    try:
        return [dict(row) for row in repository.list_active_questions(db)]
    except (errors.UndefinedTable, errors.UndefinedColumn):
        return None


def _ordered_legacy(pool):
    """Replay the exact v1 order for runs created before random draw existed."""
    by_code = {row["code"]: row for row in pool}
    ordered = [by_code[code] for code in LEGACY_CODES if code in by_code]
    return ordered or None


def draw_questions(pool, mode):
    """Stratified sampling so the topic mix stays identical to the fixed bank.

    The boss question is excluded from the quota draw and pinned to the last slot
    of level 3, so it never appears in quick mode and never lands mid-level.
    """
    quota = QUICK_QUOTA if mode == "quick" else DRAW_QUOTA
    picked = []
    for level in range(1, LEVEL_COUNT + 1):
        chosen = []
        for topic, count in quota.get(level, {}).items():
            candidates = [
                row for row in pool
                if row["level"] == level and row["topic"] == topic and not row.get("boss")
            ]
            if len(candidates) < count:
                return None
            chosen.extend(random.sample(candidates, count))
        random.shuffle(chosen)
        if mode == "quest" and level == LEVEL_COUNT:
            bosses = [row for row in pool if row["level"] == level and row.get("boss")]
            if not bosses:
                return None
            chosen.append(random.choice(bosses))
        picked.extend(chosen)
    return picked


def level_payload(level):
    meta = next((item for item in LEVELS_META if item["level"] == level), {})
    return {
        "level": level,
        "name": meta.get("name", ""),
        "hint": meta.get("hint", ""),
        "index": level,
        "of": LEVEL_COUNT,
    }


def pick_count(question):
    """How many options the student must submit; drives the confirm button state."""
    kind = question.get("kind", "single")
    if kind == "multi":
        return len(question["correct_choice_id"].split(","))
    if kind == "order":
        return len(question["choices"])
    return 1


def public_question(question):
    return {
        "code": question["code"],
        "version": question["version"],
        "kind": question.get("kind", "single"),
        "pick_count": pick_count(question),
        "snippet": question.get("snippet"),
        "boss": bool(question.get("boss")),
        "stem": question["stem"],
        "choices": question["choices"],
        "topic": question["topic"],
        "topic_label": TOPIC_LABELS.get(question["topic"], question["topic"]),
    }


def _parse_answers(row):
    try:
        data = json.loads(row["answers"] or "{}")
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("items"), list):
        data["items"] = []
    if not isinstance(data.get("levels"), list):
        data["levels"] = []
    return data


def run_questions(row, pool):
    """Resolve the frozen question order of one run."""
    payload = _parse_answers(row)
    mode = payload.get("mode", "quest")
    by_code = {row_["code"]: row_ for row_ in pool}
    codes = payload.get("codes")
    if isinstance(codes, list) and codes:
        ordered = [by_code[code] for code in codes if code in by_code]
        if len(ordered) == len(codes):
            return ordered
    if mode == "revenge":
        return []
    legacy = _ordered_legacy(pool)
    if legacy is None:
        return []
    return legacy[: MODE_TOTAL.get(mode, TOTAL_QUESTIONS)]


def public_run(row, ordered):
    payload = _parse_answers(row)
    mode = payload.get("mode", "quest")
    step = row["step"]
    total = len(ordered)
    finished = step >= total
    result = {
        "id": row["id"],
        "mode": mode,
        "step": min(step, total),
        "score": row["score"],
        "total": total,
        "finished": finished,
        "hearts_enabled": False,
        "hearts": None,
        "streak": _streak(payload["items"]),
    }
    if finished:
        return result
    question = ordered[step]
    result["level"] = level_payload(question["level"])
    if mode == "quest":
        # The step counter spans all 18 questions, so showing it next to the
        # current level reads as "level 1 has 18 questions". Expose the position
        # inside the current level too. Only meaningful in quest mode: quick has
        # its own per-level quota and revenge mixes levels.
        result["level"]["per_level"] = QUESTIONS_PER_LEVEL
        result["level"]["position"] = step - (question["level"] - 1) * QUESTIONS_PER_LEVEL + 1
    result["question"] = public_question(question)
    if mode == "quest" and question["level"] == HEART_LEVEL:
        wrong = sum(
            1 for item in payload["items"]
            if item.get("level") == question["level"] and not item.get("correct")
        )
        result["hearts_enabled"] = True
        result["hearts"] = max(0, HEARTS_PER_LEVEL - wrong)
    return result


def _streak(items):
    """[v3 A1] Consecutive correct answers at the end of the run.

    Derived from the stored answers, so it survives a reload and needs no column.
    Pure display: the combo never changes score, best_score, badge or profile.
    """
    count = 0
    for item in reversed(items):
        if not item.get("correct"):
            break
        count += 1
    return count


def _passed_levels(payload):
    return [
        entry.get("level")
        for entry in payload["levels"]
        if isinstance(entry, dict) and entry.get("passed") and entry.get("level")
    ]


def _level_states(db, user_id):
    try:
        runs = repository.list_finished_runs(db, (user_id, MISSION_ID, TOTAL_QUESTIONS))
    except (errors.UndefinedTable, errors.UndefinedColumn):
        runs = []
    cleared, best_correct = set(), {}
    for run in runs:
        payload = _parse_answers(run)
        for entry in payload["levels"]:
            if not isinstance(entry, dict):
                continue
            level = entry.get("level")
            if entry.get("passed"):
                cleared.add(level)
            previous = best_correct.get(level)
            if previous is None or entry.get("correct", 0) > previous:
                best_correct[level] = entry.get("correct", 0)
    states = []
    for meta in LEVELS_META:
        level = meta["level"]
        if level in cleared:
            state = "cleared"
        elif level == 1 or (level - 1) in cleared:
            state = "unlocked"
        else:
            state = "locked"
        states.append(
            {
                **meta,
                "state": state,
                "best_correct": best_correct.get(level),
                "total": QUESTIONS_PER_LEVEL,
            }
        )
    return states


def _topic_scores(items):
    scores = []
    for topic in TOPICS:
        answered = [item for item in items if item.get("topic") == topic]
        if not answered:
            continue
        correct = sum(1 for item in answered if item.get("correct"))
        scores.append(
            {
                "topic": topic,
                "label": TOPIC_LABELS.get(topic, topic),
                "correct": correct,
                "total": len(answered),
            }
        )
    return scores


def _reference(db, user_id):
    try:
        row = repository.find_profile_reference(db, (user_id,))
    except (errors.UndefinedTable, errors.UndefinedColumn):
        return None
    if row is None:
        return None
    if not row.get("quiz_level"):
        return None
    return {
        "level": row["quiz_level"],
        "badge": row["quiz_badge"],
        "best_score": row["quiz_best_score"],
        "topic_scores": row["quiz_topic_scores"] or [],
        "updated_at": row["quiz_updated_at"],
        "note": "闯关参考，不是能力评分；可一键采用或清空。",
    }


def _best_score(db, user_id):
    try:
        row = repository.find_best_run_score(db, (user_id, MISSION_ID, TOTAL_QUESTIONS))
    except (errors.UndefinedTable, errors.UndefinedColumn):
        return None
    return row["score"] if row else None


def _revenge_count(db, user_id):
    """Read only: never create the anchor course from a card render."""
    try:
        anchor = repository.find_anchor_course(db)
        if anchor is None:
            return 0
        rows = repository.find_revenge_versions(db, (user_id, anchor["id"]))
    except (errors.UndefinedTable, errors.UndefinedColumn):
        return 0
    return len(rows)


def card(*, user_id, get_db):
    """Compact quest summary embedded into the learning path payload."""
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return {
            "available": False,
            "title": QUEST_TITLE,
            "subtitle": QUEST_SUBTITLE,
            "description": "闯关题目尚未初始化，请先执行数据库迁移。",
            "levels": [],
            "total": TOTAL_QUESTIONS,
            "best_score": None,
            "badge": None,
            "has_unfinished": False,
            "has_progress": False,
            "revenge_count": 0,
            "modes": {},
        }
    best = _best_score(db, user_id)
    unfinished = None
    try:
        unfinished = repository.find_unfinished_run(
            db, (user_id, MISSION_ID, TOTAL_QUESTIONS)
        )
    except (errors.UndefinedTable, errors.UndefinedColumn):
        unfinished = None
    revenge = _revenge_count(db, user_id)
    anchor = repository.find_anchor_course(db)
    counts = repository.count_user_progress(
        db,
        (user_id, list(MISSION_IDS.values()), user_id, anchor["id"] if anchor else -1),
    )
    return {
        "available": True,
        "mission_id": MISSION_ID,
        "title": QUEST_TITLE,
        "subtitle": QUEST_SUBTITLE,
        "description": QUEST_DESCRIPTION,
        "levels": _level_states(db, user_id),
        "total": TOTAL_QUESTIONS,
        "best_score": best,
        "badge": badge_for(best, TOTAL_QUESTIONS) if best is not None else None,
        "has_unfinished": unfinished is not None,
        "has_progress": bool(counts["runs"] or counts["answers"]),
        "reference": _reference(db, user_id),
        "revenge_count": revenge,
        "modes": {
            "quest": {"total": TOTAL_QUESTIONS, "label": "完整闯关"},
            "quick": {"total": MODE_TOTAL["quick"], "label": "8 题速测"},
            "revenge": {"total": min(revenge, REVENGE_MAX), "label": "错题复仇"},
        },
    }


def overview(*, user_id, get_db):
    summary = card(user_id=user_id, get_db=get_db)
    return {"quest": summary, "reference": summary.get("reference")}


def _anchor_course_id(db):
    row = repository.find_anchor_course(db)
    if row:
        return row["id"]
    created = repository.insert_anchor_course(
        db, (QUEST_TITLE, ANCHOR_DESCRIPTION, ANCHOR_DURATION)
    )
    return created["id"]


def _sync_reference(db, user_id, items):
    """Only the full quest feeds the profile reference; quick/revenge never do."""
    best = _best_score(db, user_id) or 0
    badge = badge_for(best, TOTAL_QUESTIONS)
    try:
        repository.upsert_profile_reference(
            db,
            (
                user_id,
                best,
                badge["id"] if badge else None,
                suggested_level(best, TOTAL_QUESTIONS),
                Jsonb(_topic_scores(items)),
            ),
        )
    except (errors.UndefinedTable, errors.UndefinedColumn):
        db.rollback()


def _select_questions(db, pool, mode, user_id):
    """Returns (questions, error_response). Revenge pulls from the wrong-answer pool."""
    if mode != "revenge":
        selected = draw_questions(pool, mode)
        if not selected:
            return None, ({"error": "题库不足，请联系管理员补充题目"}, 503)
        return selected, None
    anchor = repository.find_anchor_course(db)
    if anchor is None:
        return None, ({"error": "暂时没有错题可以复仇，先去闯一关吧"}, 400)
    versions = [
        row["question_version"]
        for row in repository.find_revenge_versions(db, (user_id, anchor["id"]))
    ]
    by_version = {row["version"]: row for row in pool}
    selected = [by_version[version] for version in versions if version in by_version]
    if not selected:
        return None, ({"error": "暂时没有错题可以复仇，先去闯一关吧"}, 400)
    random.shuffle(selected)
    return selected[:REVENGE_MAX], None


def start(*, user_id, mode="quest", get_db):
    if mode not in MODE_TOTAL:
        return ({"error": "未知的闯关模式"}, 400)
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return ({"error": "闯关题目尚未初始化，请先执行数据库迁移"}, 503)
    mission_id = MISSION_IDS[mode]
    existing = repository.find_unfinished_run(
        db, (user_id, mission_id, MODE_TOTAL[mode])
    )
    if existing:
        return {"run": public_run(existing, run_questions(existing, pool))}
    selected, failure = _select_questions(db, pool, mode, user_id)
    if failure:
        return failure
    codes = [row["code"] for row in selected]
    row = repository.insert_run(
        db,
        (
            user_id,
            mission_id,
            json.dumps(
                {"mode": mode, "codes": codes, "items": [], "levels": []},
                ensure_ascii=False,
            ),
        ),
    )
    db.commit()
    return ({"run": public_run(row, run_questions(row, pool))}, 201)


def read_run(run_id, *, user_id, get_db):
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return ({"error": "闯关题目尚未初始化，请先执行数据库迁移"}, 503)
    row = repository.find_owned_run(db, (run_id, user_id, list(ALL_MISSION_IDS)))
    if row is None:
        return ({"error": "闯关记录不存在"}, 404)
    return {"run": public_run(row, run_questions(row, pool))}


def answer(run_id, *, user_id, data, get_db):
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return ({"error": "闯关题目尚未初始化，请先执行数据库迁移"}, 503)
    row = repository.find_owned_run(db, (run_id, user_id, list(ALL_MISSION_IDS)))
    if row is None:
        return ({"error": "闯关记录不存在"}, 404)
    mode = MODE_BY_MISSION.get(row["mission_id"], "quest")
    ordered = run_questions(row, pool)
    if not isinstance(data, dict) or type(data.get("step")) is not int:
        return ({"error": "请选择当前题目的选项"}, 400)
    if row["step"] >= len(ordered) or data["step"] != row["step"]:
        return ({"error": "题目已更新，请重新打开闯关"}, 409)
    question = ordered[row["step"]]
    if data.get("question_code") != question["code"]:
        return ({"error": "题目已更新，请重新打开闯关"}, 409)
    choice_id = data.get("choice_id")
    if not valid_choice(question, choice_id):
        return ({"error": "请选择有效选项"}, 400)

    correct = judge(question, choice_id)
    repository.record_answer(
        db,
        (user_id, _anchor_course_id(db), question["version"], choice_id, correct),
    )

    payload = _parse_answers(row)
    items = payload["items"] + [
        {
            "code": question["code"],
            "version": question["version"],
            "level": question["level"],
            "topic": question["topic"],
            "choice_id": choice_id,
            "correct": correct,
        }
    ]
    payload["items"] = items
    new_step = row["step"] + 1
    new_score = row["score"] + (1 if correct else 0)
    payload["score"] = new_score

    level_result = None
    stopped = False
    level_ends = mode == "quest" and new_step % QUESTIONS_PER_LEVEL == 0
    if level_ends:
        level_index = question["level"]
        level_items = [item for item in items if item.get("level") == level_index]
        correct_count = sum(1 for item in level_items if item.get("correct"))
        passed = correct_count >= UNLOCK_TARGET
        entry = {
            "level": level_index,
            "correct": correct_count,
            "total": len(level_items),
            "passed": passed,
        }
        payload["levels"] = [
            item for item in payload["levels"] if item.get("level") != level_index
        ] + [entry]
        level_name = next(
            (meta["name"] for meta in LEVELS_META if meta["level"] == level_index), ""
        )
        next_level = level_index + 1 if passed and level_index < LEVEL_COUNT else None
        level_result = {
            "level": level_index,
            "name": level_name,
            "correct": correct_count,
            "total": len(level_items),
            "passed": passed,
            "unlocked_level": next_level,
            "message": (
                f"本关答对 {correct_count} / {len(level_items)}"
                + (
                    f"，已解锁「{next((m['name'] for m in LEVELS_META if m['level'] == next_level), '')}」。"
                    if next_level
                    else f"，还差一点：答对 {UNLOCK_TARGET} 题即可解锁下一关，可以重做本关。"
                )
            ),
        }
        stopped = not passed

    finished = new_step >= len(ordered) or stopped
    body = {
        "correct": correct,
        "correct_choice_id": question["correct_choice_id"],
        "explanation": question["explanations"].get(choice_id) or question["explanation"],
    }
    if finished:
        payload["outcome"] = (
            "cleared" if new_step >= len(ordered) and not stopped else "stopped"
        )
        payload["max_level"] = max(_passed_levels(payload), default=0)
        nominal = MODE_TOTAL[mode]
        updated = repository.finish_run(
            db,
            (
                nominal,
                new_score,
                json.dumps(payload, ensure_ascii=False),
                run_id,
                user_id,
                nominal,
            ),
        )
        if updated is None:
            db.rollback()
            return ({"error": "本局已结束，请重新开始"}, 409)
        if mode == "quest":
            _sync_reference(db, user_id, items)
        db.commit()
        return {
            **body,
            "run": public_run(updated, run_questions(updated, pool)),
            "level_result": level_result,
            "finished": True,
        }

    updated = repository.advance_run(
        db,
        (
            1 if correct else 0,
            json.dumps(payload, ensure_ascii=False),
            run_id,
            user_id,
            row["step"],
        ),
    )
    if updated is None:
        db.rollback()
        return ({"error": "该题目已提交，请重新打开闯关"}, 409)
    db.commit()
    return {
        **body,
        "run": public_run(updated, run_questions(updated, pool)),
        "level_result": level_result,
        "finished": False,
    }


def abandon(run_id, *, user_id, get_db):
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return ({"error": "闯关题目尚未初始化，请先执行数据库迁移"}, 503)
    row = repository.find_owned_run(db, (run_id, user_id, list(ALL_MISSION_IDS)))
    if row is None:
        return ({"error": "闯关记录不存在"}, 404)
    mode = MODE_BY_MISSION.get(row["mission_id"], "quest")
    ordered = run_questions(row, pool)
    if row["step"] >= len(ordered):
        return {"run": public_run(row, ordered), "message": "本局已结束"}
    payload = _parse_answers(row)
    payload["outcome"] = "abandoned"
    payload["score"] = row["score"]
    payload["max_level"] = max(_passed_levels(payload), default=0)
    nominal = MODE_TOTAL[mode]
    updated = repository.finish_run(
        db,
        (
            nominal,
            row["score"],
            json.dumps(payload, ensure_ascii=False),
            run_id,
            user_id,
            nominal,
        ),
    )
    if updated is None:
        db.rollback()
        return ({"error": "本局已结束，请重新开始"}, 409)
    if mode == "quest":
        _sync_reference(db, user_id, payload["items"])
    db.commit()
    return {"run": public_run(updated, ordered), "message": "本局已结束，已答题目成绩保留"}


def result(*, user_id, mode="quest", get_db):
    if mode not in MODE_TOTAL:
        mode = "quest"
    db = get_db()
    pool = _load_pool(db)
    if not pool:
        return ({"error": "闯关题目尚未初始化，请先执行数据库迁移"}, 503)
    best = _best_score(db, user_id)
    reference = _reference(db, user_id)
    row = repository.find_latest_finished_run(
        db, (user_id, MISSION_IDS[mode], MODE_TOTAL[mode])
    )
    if row is None:
        return {
            "result": None,
            "mode": mode,
            "best_score": best,
            "badge": badge_for(best, TOTAL_QUESTIONS) if best is not None else None,
            "reference": reference,
        }
    payload = _parse_answers(row)
    ordered = run_questions(row, pool)
    by_code = {question["code"]: question for question in ordered}
    wrong_items = []
    for item in payload["items"]:
        if item.get("correct"):
            continue
        question = by_code.get(item.get("code"))
        if not question:
            continue
        your_choice = item.get("choice_id")
        right_choice = question["correct_choice_id"]
        wrong_items.append(
            {
                "code": question["code"],
                "stem": question["stem"],
                "your_choice": your_choice,
                # Option order was reshuffled in v3, so an answer recorded before that
                # can now coincide with the current right option. Hide it instead of
                # showing "your answer: b / right answer: b".
                "correct_choice_id": None if your_choice == right_choice else right_choice,
                "explanation": question["explanations"].get(your_choice)
                or question["explanation"],
            }
        )
    score = row["score"]
    total = len(ordered) or MODE_TOTAL[mode]
    return {
        "mode": mode,
        "result": {
            "outcome": payload.get("outcome", "stopped"),
            "score": score,
            "total": total,
            "percent": round(score * 100 / total) if total else 0,
            "badge": badge_for(score, TOTAL_QUESTIONS) if mode == "quest" else None,
            "persona": persona_for(_topic_scores(payload["items"])) if mode == "quest" else None,
            "levels": [
                entry for entry in payload["levels"] if isinstance(entry, dict)
            ],
            "topics": _topic_scores(payload["items"]),
            "wrong_items": wrong_items,
            "suggested_level": suggested_level(score, TOTAL_QUESTIONS),
        },
        "best_score": best,
        "badge": badge_for(best, TOTAL_QUESTIONS) if best is not None else None,
        "reference": reference,
    }


def adopt(*, user_id, get_db):
    db = get_db()
    reference = _reference(db, user_id)
    if not reference:
        return ({"error": "还没有闯关参考，先完成一次闯关吧"}, 400)
    repository.adopt_profile_level(db, (user_id, reference["level"]))
    db.commit()
    return {
        "level": reference["level"],
        "message": "已把闯关参考设为你的基础水平，之后仍可随时修改",
    }


def clear_progress(*, user_id, get_db):
    """Reset the quest for one student: runs, answers and the profile reference.

    Level badges are derived from finished runs (§6.2), so clearing only the
    profile reference would leave the card showing 已通关 after a reset.
    """
    db = get_db()
    repository.delete_user_runs(db, (user_id, list(MISSION_IDS.values())))
    course = repository.find_anchor_course(db)
    if course:
        repository.delete_user_results(db, (user_id, course["id"]))
    repository.clear_profile_reference(db, (user_id,))
    db.commit()
    return {"message": "已清空你的闯关记录与参考水平，可以重新开始"}


# --- [admin] question bank maintenance ---
# The bank is a global benchmark (no owner column), so only admins maintain it.
# Everything here is guarded so an edit can never break the draw: deactivating
# or deleting must leave every level/topic quota satisfiable.

QUESTION_KINDS = ("single", "multi", "order")
CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
SOURCE_LABELS = {"seed": "预置", "admin": "管理员", "teacher": "教师", "ai": "AI 生成"}


def _pool_shortages(rows):
    """Levels/topics that would fall below the draw quota for these rows."""
    counts = Counter(
        (row["level"], row["topic"])
        for row in rows
        if row["active"] and not row.get("boss")
    )
    bosses = sum(
        1 for row in rows
        if row["active"] and row.get("boss") and row["level"] == LEVEL_COUNT
    )
    missing = []
    for level, quota in DRAW_QUOTA.items():
        for topic, need in quota.items():
            have = counts.get((level, topic), 0)
            if have < need:
                missing.append(f"第 {level} 关 {TOPIC_LABELS.get(topic, topic)}（需 {need}，剩 {have}）")
    if bosses < 1:
        missing.append("第 3 关 Boss 题（需 1，剩 0）")
    return missing


def _shortage_error(shortages):
    return (
        {"error": "这样会导致完整闯关无法出题：" + "；".join(shortages) + "。请先补充题目。"},
        400,
    )


def _validate_question(data):
    """Returns (fields, error_response). Shared by create and update."""
    if not isinstance(data, dict):
        return None, ({"error": "请求内容格式不正确"}, 400)

    code = data.get("code")
    if not isinstance(code, str) or not CODE_PATTERN.match(code.strip()):
        return None, ({"error": "题目编号只能由小写字母、数字和连字符组成，长度 3–64"}, 400)
    code = code.strip()

    level = data.get("level")
    if not isinstance(level, int) or level not in range(1, LEVEL_COUNT + 1):
        return None, ({"error": f"关卡必须是 1 到 {LEVEL_COUNT} 之间的整数"}, 400)

    topic = data.get("topic")
    if topic not in TOPICS:
        return None, ({"error": f"维度必须是 {TOPICS} 之一"}, 400)

    difficulty = data.get("difficulty")
    if not isinstance(difficulty, int) or not 1 <= difficulty <= 3:
        return None, ({"error": "难度必须是 1 到 3 之间的整数"}, 400)

    kind = data.get("kind", "single")
    if kind not in QUESTION_KINDS:
        return None, ({"error": f"题型必须是 {QUESTION_KINDS} 之一"}, 400)

    stem = data.get("stem")
    if not isinstance(stem, str) or not stem.strip():
        return None, ({"error": "题干不能为空"}, 400)

    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) < 2:
        return None, ({"error": "至少要有两个选项"}, 400)
    choice_ids = []
    for choice in choices:
        if not isinstance(choice, dict):
            return None, ({"error": "每个选项都必须是对象"}, 400)
        choice_id = choice.get("id")
        text = choice.get("text")
        if not isinstance(choice_id, str) or not choice_id.strip():
            return None, ({"error": "每个选项都需要一个编号"}, 400)
        if not isinstance(text, str) or not text.strip():
            return None, ({"error": "选项内容不能为空"}, 400)
        choice_ids.append(choice_id.strip())
    if len(set(choice_ids)) != len(choice_ids):
        return None, ({"error": "选项编号不能重复"}, 400)

    correct = data.get("correct_choice_id")
    if not isinstance(correct, str) or not correct.strip():
        return None, ({"error": "必须指定正确选项"}, 400)
    correct = correct.strip()
    for part in correct.split(","):
        if part.strip() not in choice_ids:
            return None, ({"error": f"正确选项 {part.strip()} 不在选项列表里"}, 400)
    if kind == "single" and "," in correct:
        return None, ({"error": "单选题只能有一个正确选项"}, 400)

    explanation = data.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        return None, ({"error": "解析不能为空"}, 400)

    explanations = data.get("explanations") or {}
    if not isinstance(explanations, dict):
        return None, ({"error": "分选项解析必须是对象"}, 400)

    snippet = data.get("snippet")
    if snippet is not None and not isinstance(snippet, str):
        return None, ({"error": "代码片段必须是文本"}, 400)

    return {
        "code": code,
        "level": level,
        "topic": topic,
        "difficulty": difficulty,
        "kind": kind,
        "stem": stem.strip(),
        "snippet": (snippet or "").strip() or None,
        "boss": bool(data.get("boss")),
        "choices": [{"id": c["id"].strip(), "text": c["text"].strip()} for c in choices],
        "correct_choice_id": correct,
        "explanation": explanation.strip(),
        "explanations": explanations,
    }, None


def public_bank_row(row):
    return {
        "code": row["code"],
        "version": row["version"],
        "level": row["level"],
        "topic": row["topic"],
        "topic_label": TOPIC_LABELS.get(row["topic"], row["topic"]),
        "difficulty": row["difficulty"],
        "kind": row["kind"],
        "boss": bool(row.get("boss")),
        "stem": row["stem"],
        "snippet": row.get("snippet") or "",
        "choices": row["choices"],
        "correct_choice_id": row["correct_choice_id"],
        "explanation": row["explanation"],
        "source": row["source"],
        "source_label": SOURCE_LABELS.get(row["source"], row["source"]),
        "active": bool(row["active"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def bank_list(*, get_db):
    db = get_db()
    rows = [dict(row) for row in repository.list_questions(db)]
    return {
        "questions": [public_bank_row(row) for row in rows],
        "total": len(rows),
        "active": sum(1 for row in rows if row["active"]),
        "kinds": list(QUESTION_KINDS),
        "topics": [{"id": topic, "label": TOPIC_LABELS[topic]} for topic in TOPICS],
        "levels": [{"id": meta["level"], "name": meta["name"]} for meta in LEVELS_META],
    }


def create_question(data, *, get_db):
    fields, error = _validate_question(data)
    if error:
        return error
    db = get_db()
    if repository.find_question(db, (fields["code"],)) is not None:
        return ({"error": f"题目编号 {fields['code']} 已存在"}, 409)
    version = f"{fields['code']}-v1"
    try:
        repository.insert_question(
            db,
            (
                fields["code"],
                version,
                fields["level"],
                fields["topic"],
                fields["difficulty"],
                fields["stem"],
                fields["snippet"],
                fields["kind"],
                fields["boss"],
                Jsonb(fields["choices"]),
                fields["correct_choice_id"],
                fields["explanation"],
                Jsonb(fields["explanations"]),
                "admin",
                True,
            ),
        )
        db.commit()
    except errors.UniqueViolation:
        db.rollback()
        return ({"error": "题目编号或版本已存在"}, 409)
    return {"code": fields["code"], "message": "题目已创建，默认启用"}


def update_question(code, data, *, get_db):
    db = get_db()
    row = repository.find_question(db, (code,))
    if row is None:
        return ({"error": "题目不存在"}, 404)
    # Merge onto the stored row so partial edits keep the untouched fields.
    merged = {**dict(row), **{k: v for k, v in data.items() if k != "code"}, "code": code}
    fields, error = _validate_question(merged)
    if error:
        return error
    try:
        repository.update_question(
            db,
            (
                fields["level"],
                fields["topic"],
                fields["difficulty"],
                fields["stem"],
                fields["snippet"],
                fields["kind"],
                fields["boss"],
                Jsonb(fields["choices"]),
                fields["correct_choice_id"],
                fields["explanation"],
                Jsonb(fields["explanations"]),
                code,
            ),
        )
        db.commit()
    except errors.UniqueViolation:
        db.rollback()
        return ({"error": "题目保存失败，请重试"}, 409)
    return {"code": code, "message": "题目已保存"}


def set_question_active(code, active, *, get_db):
    db = get_db()
    rows = [dict(row) for row in repository.list_questions(db)]
    target = next((row for row in rows if row["code"] == code), None)
    if target is None:
        return ({"error": "题目不存在"}, 404)
    if bool(target["active"]) == active:
        return {"code": code, "active": active, "message": "状态没有变化"}
    if not active:
        shortages = _pool_shortages(
            [{**row, "active": False} if row["code"] == code else row for row in rows]
        )
        if shortages:
            return _shortage_error(shortages)
    repository.set_question_active(db, (active, code))
    db.commit()
    return {
        "code": code,
        "active": active,
        "message": "已启用，可参与抽题" if active else "已停用，不再参与抽题",
    }


def delete_question(code, *, get_db):
    db = get_db()
    row = repository.find_question(db, (code,))
    if row is None:
        return ({"error": "题目不存在"}, 404)
    hits = repository.count_question_answers(db, (row["version"],))["hits"]
    if hits:
        return (
            {"error": f"这道题已有 {hits} 条作答记录，删除会破坏历史成绩与错题本，请改用「停用」。"},
            409,
        )
    shortages = _pool_shortages(
        [r for r in (dict(x) for x in repository.list_questions(db)) if r["code"] != code]
    )
    if shortages:
        return _shortage_error(shortages)
    repository.delete_question(db, (code,))
    db.commit()
    return {"code": code, "message": "题目已删除"}
