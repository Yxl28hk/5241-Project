"""HTTP entry points for the level quest."""

from flask import Blueprint, request, session

from app.auth.security import admin_required, login_required
from app.infrastructure.database import get_db
from app.quiz import service

bp = Blueprint("quiz", __name__)


@bp.get("/api/quiz/overview")
@login_required
def overview():
    return service.overview(user_id=session.get("user_id"), get_db=get_db)


@bp.post("/api/quiz/runs")
@login_required
def start():
    data = request.get_json(silent=True)
    mode = data.get("mode", "quest") if isinstance(data, dict) else "quest"
    return service.start(user_id=session.get("user_id"), mode=mode, get_db=get_db)


@bp.get("/api/quiz/runs/<int:run_id>")
@login_required
def read_run(run_id):
    return service.read_run(run_id, user_id=session.get("user_id"), get_db=get_db)


@bp.post("/api/quiz/runs/<int:run_id>/answer")
@login_required
def answer(run_id):
    return service.answer(
        run_id,
        user_id=session.get("user_id"),
        data=request.get_json(silent=True),
        get_db=get_db,
    )


@bp.post("/api/quiz/runs/<int:run_id>/abandon")
@login_required
def abandon(run_id):
    return service.abandon(run_id, user_id=session.get("user_id"), get_db=get_db)


@bp.get("/api/quiz/result")
@login_required
def result():
    return service.result(
        user_id=session.get("user_id"),
        mode=request.args.get("mode", "quest"),
        get_db=get_db,
    )


@bp.post("/api/quiz/profile/adopt")
@login_required
def adopt():
    return service.adopt(user_id=session.get("user_id"), get_db=get_db)


@bp.delete("/api/quiz/profile/reference")
@login_required
def clear_reference():
    return service.clear_progress(user_id=session.get("user_id"), get_db=get_db)


# --- admin-only question bank maintenance ---
# The bank is a shared benchmark with no owner column, so maintenance is admin
# only; see docs/QUIZ_QUEST_SPEC.md §11.6.

@bp.get("/api/admin/quiz/questions")
@admin_required
def bank_list():
    return service.bank_list(get_db=get_db)


@bp.post("/api/admin/quiz/questions")
@admin_required
def bank_create():
    return service.create_question(request.get_json(silent=True), get_db=get_db)


@bp.put("/api/admin/quiz/questions/<code>")
@admin_required
def bank_update(code):
    return service.update_question(code, request.get_json(silent=True), get_db=get_db)


@bp.patch("/api/admin/quiz/questions/<code>/active")
@admin_required
def bank_active(code):
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("active"), bool):
        return {"error": "请指定启用或停用"}, 400
    return service.set_question_active(code, data["active"], get_db=get_db)


@bp.delete("/api/admin/quiz/questions/<code>")
@admin_required
def bank_delete(code):
    return service.delete_question(code, get_db=get_db)
