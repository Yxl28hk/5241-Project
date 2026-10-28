import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from app.infrastructure import tutor_provider


def app_for(url):
    return SimpleNamespace(
        config={
            "TUTOR_API_URL": url,
            "TUTOR_API_KEY": "test-key",
            "TUTOR_MODEL": "test-model",
        }
    )


def upstream_response(result):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(result).encode()
    return response


def tutor_context():
    return (
        {"slug": "ci-testing", "lesson": "CI automatically runs tests."},
        {"title": "Testing and CI", "description": "A test course", "progress": 0},
        "Why wait for CI?",
        [],
        {"level": "beginner"},
    )


def test_openrouter_request_limits_reasoning_and_returns_visible_answer(monkeypatch):
    upstream = MagicMock(
        return_value=upstream_response(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "CI runs checks before merge."},
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(tutor_provider, "urlopen", upstream)

    answer = tutor_provider.model_answer(
        app_for("https://openrouter.ai/api/v1/chat/completions"),
        *tutor_context(),
    )

    payload = json.loads(upstream.call_args.args[0].data)
    assert payload["max_tokens"] == 1800
    assert payload["reasoning"] == {"effort": "low"}
    assert answer == "CI runs checks before merge."


def test_empty_length_limited_answer_does_not_expose_reasoning(monkeypatch):
    upstream = MagicMock(
        return_value=upstream_response(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": None,
                            "reasoning": "private model reasoning",
                        },
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(tutor_provider, "urlopen", upstream)

    with pytest.raises(tutor_provider.TutorUnavailable) as error:
        tutor_provider.model_answer(
            app_for("https://openrouter.ai/api/v1/chat/completions"),
            *tutor_context(),
        )

    assert "private model reasoning" not in str(error.value)
    assert "回答额度" in str(error.value)


def test_other_compatible_providers_do_not_receive_openrouter_options(monkeypatch):
    upstream = MagicMock(
        return_value=upstream_response(
            {"choices": [{"message": {"content": "Answer"}}]}
        )
    )
    monkeypatch.setattr(tutor_provider, "urlopen", upstream)

    tutor_provider.model_answer(
        app_for("https://provider.example/v1/chat/completions"),
        *tutor_context(),
    )

    payload = json.loads(upstream.call_args.args[0].data)
    assert payload["max_tokens"] == 1800
    assert "reasoning" not in payload


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "认证失败"),
        (402, "额度不足"),
        (403, "拒绝了请求"),
        (404, "地址或模型不可用"),
        (429, "请求过多"),
    ],
)
def test_provider_http_errors_are_actionable_and_do_not_leak_body(
    monkeypatch, status, message
):
    error = HTTPError(
        "https://provider.example/private-path",
        status,
        "upstream error",
        {},
        None,
    )
    error.read = lambda *_args, **_kwargs: b"secret upstream details"
    monkeypatch.setattr(tutor_provider, "urlopen", MagicMock(side_effect=error))

    with pytest.raises(tutor_provider.TutorUnavailable) as failure:
        tutor_provider.model_answer(
            app_for("https://openrouter.ai/api/v1/chat/completions"),
            *tutor_context(),
        )

    assert message in str(failure.value)
    assert "secret" not in str(failure.value)
    assert "private-path" not in str(failure.value)
