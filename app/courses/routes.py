"""HTTP entry points for courses."""

from flask import Blueprint, request, session

from app.auth.security import teacher_or_admin_required
from app.courses import service
from app.infrastructure.database import get_db

bp = Blueprint("courses", __name__)


@bp.get("/api/courses")
def courses():
    result = service.courses(filters=request.args, get_db=get_db)
    return result


@bp.post("/api/courses")
@teacher_or_admin_required
def create_course():
    result = service.create_course(
        user_id=session.get("user_id"),
        form=request.form,
        files=request.files,
        get_db=get_db,
    )
    return result


@bp.get("/api/profile/courses")
@teacher_or_admin_required
def my_courses():
    result = service.my_courses(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.get("/api/courses/<int:course_id>/learners")
@teacher_or_admin_required
def course_learners(course_id):
    result = service.course_learners(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.delete("/api/courses/<int:course_id>/learners/<int:user_id>")
@teacher_or_admin_required
def remove_course_learner(course_id, user_id):
    result = service.remove_course_learner(
        course_id, user_id, actor_id=session["user_id"], get_db=get_db
    )
    return result


@bp.delete("/api/courses/<int:course_id>")
@teacher_or_admin_required
def delete_course(course_id):
    result = service.delete_course(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result
