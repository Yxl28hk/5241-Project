from app.learning import repository

"Small, explainable learning paths built from the existing short lessons."

from app.learning.content import MODULES

GOALS = {
    "collaboration": "协作开发入门",
    "quality": "测试与发布",
    "engineering": "软件工程实践",
}

LEVELS = {"beginner": "零基础", "intermediate": "入门", "experienced": "有经验"}

PATHS = [
    {
        "id": "collaboration",
        "title": "团队协作入门",
        "goal": "collaboration",
        "level": "beginner",
        "description": "从一次小修改开始，学会用分支、PR 和自动检查与同伴协作。",
        "outcome": "能说明一次代码修改从分支到合并需要哪些证据。",
        "deliverable": "完成一份包含验证证据的 PR 交接说明",
        "focus": "重点练习：分支协作、评审与交接",
        "slugs": ["git-pr", "ci-testing"],
        "stages": ["协作基础", "质量关卡"],
    },
    {
        "id": "quality",
        "title": "测试与发布基础",
        "goal": "quality",
        "level": "intermediate",
        "description": "围绕失败测试与上线事故，练习验证、发布和恢复的基本判断。",
        "outcome": "能为一次发布列出测试、监控和回滚检查清单。",
        "deliverable": "整理 CI 调查步骤与发布恢复清单",
        "focus": "重点练习：失败复现、监控与恢复",
        "slugs": ["ci-testing", "safe-release"],
        "stages": ["测试证据", "发布与恢复"],
    },
    {
        "id": "engineering",
        "title": "软件工程流程体验",
        "goal": "engineering",
        "level": "experienced",
        "description": "串联代码协作、持续集成与安全发布，再挑战 Release Rescue。",
        "outcome": "能解释一个变更从开发、验证到交付的完整流程。",
        "deliverable": "串联三节课的成果，再完成 Release Rescue 决策挑战",
        "focus": "重点练习：开发、验证与交付的衔接",
        "slugs": ["git-pr", "ci-testing", "safe-release"],
        "stages": ["协作开发", "持续验证", "安全交付"],
    },
]

DEFAULT_PROFILE = {"goal": "", "level": "", "weekly_hours": None, "updated_at": None}


def learning_status(progress, enrolled):
    if progress == 100:
        return "completed"
    return "in_progress" if enrolled or progress > 0 else "not_started"


def read_profile(db, user_id):
    row = repository.find_profile(db, (user_id,))
    return dict(row) if row else dict(DEFAULT_PROFILE)


def recommend_paths(profile, catalog):
    """Deterministic ranking; never claim to have measured a student's ability."""
    ranked = []
    for path in catalog:
        score = 0
        reasons = []
        if profile["goal"] == path["goal"]:
            score += 6
            reasons.append("与你的「" + GOALS[path["goal"]] + "」目标匹配")
        if profile["level"] == path["level"]:
            score += 3
            reasons.append("适合你填写的「" + LEVELS[path["level"]] + "」基础")
        if profile["level"] == "beginner" and path["id"] == "collaboration":
            score += 5
            reasons.append("建议先建立协作与测试基础，再进入完整工程实践")
        if not reasons:
            reasons.append("可浏览的预置路径；完善目标与基础后会优先展示更匹配的内容")
        ranked.append(
            {"path_id": path["id"], "score": score, "reason": "；".join(reasons) + "。"}
        )
    return sorted(ranked, key=lambda item: -item["score"])


def learning_snapshot(db, user_id):
    profile = read_profile(db, user_id)
    preference = repository.find_active_path(db, (user_id,))
    active_id = preference["active_path_slug"] if preference else None
    rows = repository.list_lesson_progress(db, (user_id,))
    by_slug = {
        row["slug"]: {**module, **dict(row), "title": module["title"]}
        for row in rows
        for module in MODULES
        if module["slug"] == row["slug"]
    }
    for module in by_slug.values():
        module["status"] = learning_status(module["progress"], module["enrolled"])
    catalog = []
    for template in PATHS:
        lessons = [
            {**by_slug[slug], "stage": stage}
            for slug, stage in zip(template["slugs"], template["stages"])
            if slug in by_slug
        ]
        complete = sum((lesson["progress"] == 100 for lesson in lessons))
        minutes = len(lessons) * 5
        catalog.append(
            {
                **{k: v for k, v in template.items() if k not in {"slugs", "stages"}},
                "level_label": LEVELS[template["level"]],
                "modules": lessons,
                "total": len(lessons),
                "completed": complete,
                "completion_percent": round(complete * 100 / len(lessons))
                if lessons
                else 0,
                "minutes": minutes,
                "available": len(lessons) == len(template["slugs"]),
            }
        )
    active = next((path for path in catalog if path["id"] == active_id), None)
    modules = (
        active["modules"]
        if active
        else [by_slug[m["slug"]] for m in MODULES if m["slug"] in by_slug]
    )
    next_id = next((m["id"] for m in modules if m["progress"] < 100), None)
    position = repository.find_path_position(db, (user_id, active_id or ""))
    resume_id = (
        position["course_id"]
        if position and any((m["id"] == position["course_id"] for m in modules))
        else None
    )
    return {
        "profile": profile,
        "active_path_id": active_id if active else None,
        "active_path": active,
        "catalog": catalog,
        "recommendations": recommend_paths(
            profile, [p for p in catalog if p["available"]]
        ),
        "modules": modules,
        "completed": sum((m["progress"] == 100 for m in modules)),
        "progress": round(sum((m["progress"] for m in modules)) / len(modules))
        if modules
        else 0,
        "completion_percent": round(
            sum((m["progress"] == 100 for m in modules)) * 100 / len(modules)
        )
        if modules
        else 0,
        "next_course_id": next_id,
        "resume_course_id": resume_id
        or next_id
        or (modules[0]["id"] if modules else None),
        "has_resume": resume_id is not None,
    }


def record_visit(db, user_id, course_id):
    repository.update_last_visit(db, (user_id, course_id))
    preference = repository.find_visit_path(db, (user_id,))
    if not preference:
        return
    template = next(
        (p for p in PATHS if p["id"] == preference["active_path_slug"]), None
    )
    lesson = repository.find_lesson_slug(db, (course_id,))
    if template and lesson and (lesson["slug"] in template["slugs"]):
        repository.upsert_path_position(db, (user_id, template["id"], course_id))
