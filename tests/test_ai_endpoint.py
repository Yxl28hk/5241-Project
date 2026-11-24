"""Regression for the complete Chat Completions URL supplied to teacher AI."""
import json
from unittest.mock import Mock, MagicMock
import pytest
from app.studio import course_ai
from app.infrastructure import tutor_provider


@pytest.mark.parametrize('base,expected',[
    ('https://openrouter.ai/api/v1/chat/completions','https://openrouter.ai/api/v1/messages'),
    ('https://openrouter.ai/api/v1/messages/','https://openrouter.ai/api/v1/messages'),
    ('https://openrouter.ai/api','https://openrouter.ai/api/v1/messages'),
    ('https://openrouter.ai','https://openrouter.ai/api/v1/messages'),
    ('https://gateway.example','https://gateway.example/v1/messages'),
    ('https://gateway.example/v1','https://gateway.example/v1/messages'),
    ('https://gateway.example/v1/messages','https://gateway.example/v1/messages'),
])
def test_teacher_request_uses_supported_messages_url(monkeypatch,base,expected):
    monkeypatch.setattr(course_ai,'ai_settings',lambda:dict(base=base,key='test-secret',model='test-model'))
    opener=MagicMock();monkeypatch.setattr(course_ai,'build_opener',lambda *args:opener)
    monkeypatch.setattr(course_ai,'read_message',lambda *args,**kwargs:{'content':[],'usage':{}})
    monkeypatch.setattr(course_ai,'response_data',lambda *args:{})
    monkeypatch.setattr(course_ai,'validate_result',lambda *args:{'course':{}})
    course_ai.request_course({'pages':[],'warnings':[]},'auto')
    request=opener.open.call_args.args[0]
    assert request.full_url==expected
    payload=json.loads(request.data)
    assert payload['tool_choice']=={'type':'tool','name':'submit_course'}
    assert payload['tools'][0]['input_schema']['type']=='object'
    assert 'test-secret' not in request.full_url and 'test-secret' not in request.data.decode()
    app=Mock(config={'TUTOR_USE_STUDIO_AI':True})
    assert tutor_provider.tutor_settings(app)['url']==expected


@pytest.mark.parametrize('base',[
    'http://openrouter.ai/api/v1','https://gateway.example/chat/completions',
    'https://openrouter.ai.evil.example/api/v1/chat/completions',
    'https://openrouter.ai/api/v1?api_key=secret',
    'https://user:password@openrouter.ai/api/v1',
])
def test_invalid_protocol_or_credential_bearing_endpoint_rejected_before_network(base):
    with pytest.raises(course_ai.CourseAIError) as error:
        course_ai.messages_endpoint(base)
    assert error.value.code=='invalid_endpoint'
