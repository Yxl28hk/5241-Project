"""HTTP entry points for tutor."""

from flask import Blueprint, current_app, request, session

from app.auth.security import login_required
from app.infrastructure.database import get_db
from app.tutor import service

bp = Blueprint("tutor", __name__)


@bp.post("/api/courses/<int:course_id>/conversation")
@login_required
def restore_conversation(course_id):
    result = service.restore_conversation(
        course_id, user_id=session.get("user_id"), get_db=get_db
    )
    return result


@bp.delete("/api/courses/<int:course_id>/conversation")
@login_required
def new_conversation(course_id):
    result = service.new_conversation(
        course_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result


@bp.get("/api/prototype/config")
def config():
    result = service.config(app=current_app)
    return result


@bp.post("/api/tutor")
@login_required
def tutor():
    result = service.tutor(
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
        app=current_app,
    )
    return result
