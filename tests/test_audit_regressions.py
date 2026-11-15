"""Malformed requests and question edits must not break learning or review."""
from unittest.mock import Mock

import pytest

from app import create_app
from app.auth import security, lifecycle
from app.quiz import service, routes, repository
from app.quiz.content import question_rows, valid_choice, judge


@pytest.mark.parametrize("payload", [None, [], [1], "text", 4, True])
def test_question_update_rejects_non_objects_before_database(payload):
    db = Mock(side_effect=AssertionError("unexpected database access"))
    assert service.update_question("sample", payload, get_db=db)[1] == 400
    db.assert_not_called()


@pytest.mark.parametrize("mode", [[], {}, None, True, 7])
def test_quiz_start_rejects_invalid_mode(mode):
    db = Mock(side_effect=AssertionError("unexpected database access"))
    assert service.start(user_id=1, mode=mode, get_db=db)[1] == 400


def test_malformed_admin_requests_return_actionable_errors(monkeypatch):
    app = create_app({"TESTING": True, "SECRET_KEY": "audit-test"})
    client = app.test_client()
    monkeypatch.setattr(security, "get_db", Mock())
    monkeypatch.setattr(security, "find_role", lambda *_: {"role": "admin"})
    fail = Mock(side_effect=AssertionError("invalid request reached database"))
    monkeypatch.setattr(lifecycle, "get_db", fail)
    monkeypatch.setattr(routes, "get_db", fail)
    with client.session_transaction() as session:
        session["user_id"] = 1
    for payload in [[1], "text", True, 9]:
        assert client.patch('/api/admin/quiz/questions/sample/active', json=payload).status_code == 400
    for decision in [[], {}, None, True]:
        response = client.post('/api/admin/teacher-applications/2/review', json={"decision": decision, "reason": "Reviewed"})
        assert response.status_code == 400


@pytest.mark.parametrize("changes", [
    {"level": True}, {"difficulty": True},
    {"kind": "order", "correct_choice_id": "a,b"},
    {"kind": "multi", "correct_choice_id": "a,a"},
    {"kind": "multi", "correct_choice_id": "a"},
    {"kind": "multi", "correct_choice_id": "a,b,c,d"},
    {"choices": [{"id": "a,b", "text": "Bad ID"}, {"id": "b", "text": "B"}]},
])
def test_bank_cannot_save_unanswerable_questions(changes):
    question = {**question_rows()[0], **changes}
    assert service._validate_question(question)[1][1] == 400


def test_answer_whitespace_is_normalized_and_remains_playable():
    question = {**question_rows()[0], "kind": "multi", "correct_choice_id": " a, b "}
    fields, error = service._validate_question(question)
    assert error is None
    assert fields["correct_choice_id"] == "a,b"
    assert valid_choice(fields, "a,b") and judge(fields, "a,b")


def test_edit_cannot_remove_the_last_required_boss(monkeypatch):
    monkeypatch.setattr(repository, "count_question_answers", lambda *_: {"hits": 0})
    pool = [{**q, "active": True} for q in question_rows()]
    boss = next(q for q in pool if q["boss"])
    monkeypatch.setattr(repository, "find_question", lambda *_: boss)
    monkeypatch.setattr(repository, "list_questions", lambda *_: pool)
    write = Mock(side_effect=AssertionError("invalid edit saved"))
    monkeypatch.setattr(repository, "update_question", write)
    result = service.update_question(boss["code"], {"boss": False}, get_db=Mock())
    assert result[1] == 400 and "Boss" in result[0]["error"]
    write.assert_not_called()


def test_answered_question_cannot_be_rewritten(monkeypatch):
    question = {**question_rows()[0], "active": True}
    monkeypatch.setattr(repository, "find_question", lambda *_: question)
    monkeypatch.setattr(repository, "count_question_answers", lambda *_: {"hits": 1})
    write = Mock(side_effect=AssertionError("historical question overwritten"))
    monkeypatch.setattr(repository, "update_question", write)
    response = service.update_question(question["code"], {"stem": "replacement"}, get_db=Mock())
    assert response[1] == 409 and "作答记录" in response[0]["error"]
    write.assert_not_called()


def test_unanswered_question_can_still_be_edited(monkeypatch):
    question = {**question_rows()[0], "active": False}
    monkeypatch.setattr(repository, "find_question", lambda *_: question)
    monkeypatch.setattr(repository, "count_question_answers", lambda *_: {"hits": 0})
    write = Mock()
    monkeypatch.setattr(repository, "update_question", write)
    db = Mock()
    response = service.update_question(question["code"], {"stem": "replacement"}, get_db=lambda: db)
    assert response["message"] == "题目已保存"
    write.assert_called_once()
    db.commit.assert_called_once()
