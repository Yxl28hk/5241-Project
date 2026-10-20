"""HTTP entry points for learning."""

from flask import Blueprint, request, session

from app.auth.security import login_required
from app.infrastructure.database import get_db
from app.learning import service

bp = Blueprint("learning", __name__)


@bp.get("/api/profile/learning")
@login_required
def learning_courses():
    result = service.learning_courses(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.post("/api/courses/<int:course_id>/learn")
@login_required
def start_learning(course_id):
    result = service.start_learning(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.delete("/api/profile/learning/<int:course_id>")
@login_required
def stop_learning(course_id):
    result = service.stop_learning(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.get("/api/learning-profile")
@login_required
def learning_profile():
    result = service.learning_profile(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.patch("/api/learning-profile")
@login_required
def save_learning_profile():
    result = service.save_learning_profile(
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result


@bp.post("/api/learning-path/select")
@login_required
def select_learning_path():
    result = service.select_learning_path(
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result


@bp.get("/api/courses/<int:course_id>/lesson")
@login_required
def course_lesson(course_id):
    result = service.course_lesson(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.get("/api/courses/<int:course_id>/exercise")
@login_required
def read_exercise(course_id):
    result = service.read_exercise(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.post("/api/courses/<int:course_id>/exercise")
@login_required
def submit_exercise(course_id):
    result = service.submit_exercise(
        course_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result


@bp.get("/api/courses/<int:course_id>/notebook")
@login_required
def read_notebook(course_id):
    result = service.read_notebook(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.patch("/api/courses/<int:course_id>/notebook")
@login_required
def save_notebook(course_id):
    result = service.save_notebook(
        course_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result


@bp.get("/api/learning-path")
@login_required
def path():
    result = service.path(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.patch("/api/courses/<int:course_id>/progress")
@login_required
def progress(course_id):
    result = service.progress(
        course_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result
