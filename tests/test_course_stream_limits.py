"""Provider stream regressions: unfinished arguments must never become a draft."""
import io
import json
from unittest.mock import MagicMock

import pytest

from app.studio import course_ai
from app.studio.course_stream import read_message, StreamError


class Response(io.BytesIO):
    headers = {'Content-Type': 'text/event-stream'}


def stream(arguments, reason='tool_use', usage=None):
    events = [
        {'type': 'message_start', 'message': {'content': [], 'usage': usage}},
        {'type': 'content_block_start', 'index': 0,
         'content_block': {'type': 'tool_use', 'name': 'submit_course', 'input': {}}},
        {'type': 'content_block_delta', 'index': 0,
         'delta': {'type': 'input_json_delta', 'partial_json': arguments}},
        {'type': 'content_block_stop', 'index': 0},
        {'type': 'message_delta', 'delta': {'stop_reason': reason}, 'usage': None},
        {'type': 'message_stop'},
    ]
    return Response(''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode())


@pytest.mark.parametrize('arguments', ['{"title":"unfinished', '{"title":"complete"}'])
def test_output_limit_wins_over_partial_json_and_rejects_even_valid_prefix(arguments):
    with pytest.raises(StreamError) as error:
        read_message(stream(arguments, reason='max_tokens', usage={}))
    assert error.value.code == 'output_limit'


def test_complete_response_with_null_optional_usage_is_accepted():
    result = read_message(stream('{"title":"完整课程"}'))
    assert result['content'][0]['input'] == {'title': '完整课程'}
    assert result['usage'] == {}


def test_complete_response_with_malformed_arguments_is_not_repaired():
    with pytest.raises(StreamError) as error:
        read_message(stream('{"title":"unfinished', usage={}))
    assert error.value.code == 'invalid_tool_json'


def test_missing_message_stop_never_accepts_closed_tool_block():
    raw = stream('{"title":"complete"}', usage={}).getvalue()
    raw = raw[:raw.rfind(b'data:')]
    with pytest.raises(StreamError) as error:
        read_message(Response(raw))
    assert error.value.code == 'incomplete_response'


def test_nonstreaming_limit_has_same_error_code():
    with pytest.raises(course_ai.CourseAIError) as error:
        course_ai.response_data({'content': [], 'stop_reason': 'max_tokens'})
    assert error.value.code == 'output_limit'


@pytest.mark.parametrize('base,is_router', [
    ('https://openrouter.ai/api/v1/chat/completions', True),
    ('https://claude-gateway.example/v1', False),
])
def test_provider_budget_and_error_reporting_without_retry(monkeypatch,base,is_router):
    monkeypatch.setattr(course_ai,'ai_settings',lambda:dict(base=base,key='test-secret',model='test-model'))
    opener=MagicMock()
    opener.open.return_value.__enter__.return_value=stream('{"title":"unfinished',reason='max_tokens',usage={})
    monkeypatch.setattr(course_ai,'build_opener',lambda *args:opener)
    with pytest.raises(course_ai.CourseAIError) as error:
        course_ai.request_course({'pages':[],'warnings':[]},'auto')
    assert error.value.code=='output_limit'
    assert '原草稿仍保留' in str(error.value)
    assert 'test-secret' not in str(error.value)
    assert opener.open.call_count==1
    payload=json.loads(opener.open.call_args.args[0].data)
    if is_router:
        assert payload['thinking']=={'type':'disabled'}
    else:
        assert 'thinking' not in payload
    assert payload['max_tokens']==4500
