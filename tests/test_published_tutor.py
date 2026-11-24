from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.tutor import service
from app.infrastructure.tutor_provider import TutorUnavailable
from app.learning.study import focus_context

CONTENT = {"sections": [{"title": "回滚窗口", "body": "连续七分钟超过阈值。"}],
           "task": "解释回滚判断", "checklist": "检查连续性", "reference": "中断后重新计时。",
           "example": "第三分钟下降到阈值以下。", "objectives": "理解回滚条件"}


@pytest.fixture
def published(monkeypatch):
    monkeypatch.setattr(service, "read_studio", lambda *a: CONTENT)
    monkeypatch.setattr(service, "read_profile", lambda *a: {})
    db = Mock()
    app = SimpleNamespace(config={})
    course = {"id": 1, "title": "演示", "description": "简介", "progress": 0}
    def reply(**values):
        return service.tutor_reply(app, lambda:db, {"message":"请解释",**values}, course, None, 1)
    return reply


def test_published_section_fallback_and_invalid_focus(published):
    result=published(context_key="section-0",mode="guided-demo")
    assert "连续七分钟" in result["answer"] and "不是 AI" in result["answer"]
    assert published(context_key="section-99")[1] == 400
    assert published(context_key="section--1")[1] == 400


def test_teacher_reference_is_preserved_without_model(published,monkeypatch):
    model=Mock(side_effect=AssertionError("must not call model"))
    monkeypatch.setattr(service,"model_answer",model)
    result=published(context_key="task",action="reference")
    assert result["answer"]==CONTENT["reference"]
    assert result["mode"]=="guided-demo" and "教师" in result["label"]


def test_published_task_hint_and_fallback(published,monkeypatch):
    monkeypatch.setattr(service,"tutor_mode",lambda *a:"live")
    monkeypatch.setattr(service,"course_materials",lambda *a:{"sources":[],"warnings":[]})
    model=Mock(return_value="先想想窗口是否连续。")
    monkeypatch.setattr(service,"model_answer",model)
    result=published(context_key="task",action="hint",hint_step=1)
    assert result["mode"]=="live"
    assert model.call_args.args[2]["focus"]["text"]==CONTENT["task"]
    assert "不直接给出完整答案" in model.call_args.args[3]
    result=published(context_key="task",action="hint",hint_step=2,mode="guided-demo")
    assert CONTENT["checklist"] in result["answer"]


def test_live_failure_remains_explicit_and_original_can_be_requested(published,monkeypatch):
    monkeypatch.setattr(service,"tutor_mode",lambda *a:"live")
    monkeypatch.setattr(service,"course_materials",lambda *a:{"sources":[],"warnings":[]})
    monkeypatch.setattr(service,"model_answer",Mock(side_effect=TutorUnavailable("暂时不可用")))
    assert published(context_key="section-0")[1]==502
    fallback=published(context_key="section-0",mode="guided-demo")
    assert fallback["mode"]=="guided-demo" and CONTENT["sections"][0]["body"] in fallback["answer"]


def test_no_reference_and_cross_course_content_are_not_inferred(published,monkeypatch):
    monkeypatch.setattr(service,"read_studio",lambda *a:{"task":"Only task"})
    assert published(context_key="task",action="reference")[1]==400
    assert published(context_key="section-0")[1]==400
    assert focus_context(None,{"studio":CONTENT},"example")["text"]==CONTENT["example"]
