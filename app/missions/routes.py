"""HTTP entry points for missions."""

from flask import Blueprint, request, session

from app.auth.security import login_required
from app.infrastructure.database import get_db
from app.missions import service

bp = Blueprint("missions", __name__)


@bp.post("/api/missions/release-rescue/start")
@login_required
def start():
    result = service.start(user_id=session.get("user_id"), get_db=get_db)
    return result


@bp.post("/api/missions/attempts/<int:attempt_id>/answer")
@login_required
def answer(attempt_id):
    result = service.answer(
        attempt_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )
    return result
