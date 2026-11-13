"""Courses business rules. HTTP parsing and session changes belong to routes."""

from secrets import token_hex
from typing import Any, Mapping

from werkzeug.utils import secure_filename

from app.courses import repository
from app.infrastructure.storage import allowed_file, upload_folder


def course_json(db, row: Mapping[str, Any]) -> dict:
    course = dict(row)
    course["type"] = course.pop("resource_type")
    course["file_url"] = (
        f"/uploads/{course['filename']}" if course["filename"] else None
    )
    course["learner_count"] = repository.count_learners(db, (course["id"],))["count"]
    return course


def managed_course(db, user_id, course_id) -> Mapping[str, Any] | None:
    user = repository.find_actor_role(db, (user_id,))
    if user and user["role"] == "admin":
        return repository.find_course(db, (course_id,))
    return repository.find_owned_course(db, (course_id, user_id))


def courses(*, filters, get_db):
    query = str(filters.get("q", "")).strip()
    category = str(filters.get("category", "全部")).strip()
    rows = repository.search_courses(get_db(), query, category)
    return {"courses": [course_json(get_db(), row) for row in rows]}


def create_course(*, user_id, form, files, get_db):
    title = str(form.get("title", "")).strip()
    category = str(form.get("category", "")).strip()
    resource_type = str(form.get("type", "")).strip().lower()
    description = str(form.get("description", "")).strip()
    file = files.get("file")
    if not title or category not in {"设计", "技术", "商业", "人文"}:
        return ({"error": "请填写课程名称并选择有效分类"}, 400)
    if file is None or not file.filename or (not allowed_file(file.filename)):
        return ({"error": "请选择 PDF、Word、PPT 或视频文件"}, 400)
    if resource_type not in {"pdf", "word", "ppt", "video"}:
        return ({"error": "不支持的资源类型"}, 400)
    user = repository.find_author(get_db(), (user_id,))
    safe_name = secure_filename(file.filename)
    stored_name = f"{token_hex(12)}_{safe_name}"
    file.save(upload_folder() / stored_name)
    cover = {"pdf": "business", "video": "tech", "ppt": "humanities", "word": "design"}[
        resource_type
    ]
    db = get_db()
    cursor = repository.insert_course(
        db,
        (
            title,
            category,
            resource_type,
            description or f"包含 {file.filename} 的学习资料",
            user["name"],
            "新资源",
            cover,
            "刚刚上传",
            stored_name,
            user_id,
        ),
    )
    course_id = cursor.fetchone()["id"]
    db.commit()
    row = repository.find_created_course(db, (course_id,))
    return ({"course": course_json(get_db(), row)}, 201)


def my_courses(*, user_id, get_db):
    db = get_db()
    current_user = repository.find_manager_role(db, (user_id,))
    if current_user and current_user["role"] == "admin":
        rows = repository.list_all_courses(db)
    else:
        rows = repository.list_owned_courses(db, (user_id,))
    return {"courses": [course_json(get_db(), row) for row in rows]}


def course_learners(course_id: int, *, user_id, get_db):
    if managed_course(get_db(), user_id, course_id) is None:
        return ({"error": "没有权限查看该课程的学习人员"}, 404)
    rows = repository.list_learners(get_db(), (course_id,))
    return {"learners": [dict(row) for row in rows]}


def remove_course_learner(course_id: int, user_id: int, *, actor_id, get_db):
    if managed_course(get_db(), actor_id, course_id) is None:
        return ({"error": "没有权限管理该课程的学习人员"}, 404)
    cursor = repository.delete_learner(get_db(), (course_id, user_id))
    if cursor.rowcount == 0:
        return ({"error": "该用户不在课程学习名单中"}, 404)
    get_db().commit()
    return {"message": "已移除该学习人员"}


def delete_course(course_id: int, *, user_id, get_db):
    db = get_db()
    current_user = repository.find_deletion_role(db, (user_id,))
    if current_user and current_user["role"] == "admin":
        course = repository.find_course_file(db, (course_id,))
    else:
        course = repository.find_owned_course_file(db, (course_id, user_id))
    if course is None:
        return ({"error": "没有权限删除该课程，或课程不存在"}, 404)
    repository.delete_course_learning(db, (course_id,))
    if current_user and current_user["role"] == "admin":
        repository.delete_course(db, (course_id,))
    else:
        repository.delete_owned_course(db, (course_id, user_id))
    db.commit()
    if course["filename"]:
        stored_file = upload_folder() / course["filename"]
        if stored_file.is_file():
            stored_file.unlink()
    return {"message": "课程已删除"}


def learner_detail(course_id, learner_id, *, actor_id, get_db):
    db=get_db();course=managed_course(db,actor_id,course_id)
    if course is None:return {"error":"没有权限查看该课程的学习人员"},404
    learner=repository.learner_detail(db,course_id,learner_id)
    if learner is None:return {"error":"该学习者当前未加入这门课程"},404
    from app.learning.study import EXERCISES
    definitions={item["version"]:item for item in EXERCISES.values()}
    results=[]
    for row in repository.learner_exercises(db,course_id,learner_id):
        item=dict(row);definition=definitions.get(item["question_version"],{})
        item["question"]=definition.get("question","历史版本练习（题干暂不可用）")
        item["answer"]=next((c["text"] for c in definition.get("choices",[]) if c["id"]==item["choice_id"]),"历史选项（内容暂不可用）")
        results.append(item)
    return {"learner":dict(learner),"course":{"id":course_id,"title":course["title"]},"exercises":results}
