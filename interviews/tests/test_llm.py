import json
import logging

import pytest

from interviews import llm

MESSAGES = [{"role": "user", "content": "Reply with JSON. Secret resume text."}]


@pytest.fixture
def both_keys(settings):
    settings.GEMINI_API_KEY = "gemini-test-key"
    settings.GROQ_API_KEY = "groq-test-key"
    settings.GEMINI_MODEL = "gemini-test-model"
    settings.GROQ_MODEL = "groq-test-model"
    return settings


def completion(content):
    return 200, json.dumps({"choices": [{"message": {"content": content}}]})


class FakeTransport:
    """Answers each provider with a scripted reply and records the calls."""

    def __init__(self, replies):
        self.replies = replies  # provider name -> (status, body) or an exception
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        name = "gemini" if "googleapis" in url else "groq"
        self.calls.append({"provider": name, "headers": headers, "payload": payload})
        reply = self.replies[name]
        if isinstance(reply, Exception):
            raise reply
        return reply


def ask(transport, **kwargs):
    return llm.chat_json(MESSAGES, purpose="test", max_tokens=100, transport=transport, **kwargs)


def test_first_provider_answers(both_keys):
    transport = FakeTransport({"gemini": completion('{"ok": true}'), "groq": completion('{"ok": false}')})

    assert ask(transport) == {"ok": True}
    assert [call["provider"] for call in transport.calls] == ["gemini"]
    call = transport.calls[0]
    assert call["headers"]["Authorization"] == "Bearer gemini-test-key"
    assert call["payload"]["model"] == "gemini-test-model"
    assert call["payload"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("gemini_reply", [
    (429, json.dumps({"error": {"message": "Quota exceeded"}})),
    (503, "overloaded"),
    llm.ProviderError("request failed: timed out"),
    completion("this is not json"),
    completion("[1, 2, 3]"),
    (200, json.dumps({"unexpected": "shape"})),
])
def test_falls_back_to_groq_when_gemini_fails(both_keys, gemini_reply):
    transport = FakeTransport({"gemini": gemini_reply, "groq": completion('{"from": "groq"}')})

    assert ask(transport) == {"from": "groq"}
    assert [call["provider"] for call in transport.calls] == ["gemini", "groq"]


def test_reply_failing_validation_moves_to_next_provider(both_keys):
    transport = FakeTransport({"gemini": completion('{"questions": []}'), "groq": completion('{"questions": ["q"]}')})

    def needs_questions(reply):
        if not reply["questions"]:
            raise llm.ProviderError("no questions")
        return reply

    assert ask(transport, validate=needs_questions) == {"questions": ["q"]}


def test_all_providers_failing_raises(both_keys):
    transport = FakeTransport({"gemini": (429, "{}"), "groq": (500, "{}")})

    with pytest.raises(llm.AIUnavailable):
        ask(transport)


def test_no_keys_raises_without_calling_anything(settings):
    transport = FakeTransport({})

    with pytest.raises(llm.AIUnavailable):
        ask(transport)
    assert transport.calls == []


def test_provider_without_key_is_skipped(settings):
    settings.GROQ_API_KEY = "groq-test-key"
    transport = FakeTransport({"groq": completion('{"ok": true}')})

    assert ask(transport) == {"ok": True}
    assert [call["provider"] for call in transport.calls] == ["groq"]


def test_order_comes_from_settings(both_keys):
    both_keys.AI_PROVIDER_ORDER = ["groq", "gemini", "unknown"]

    assert [provider.name for provider in llm.configured_providers()] == ["groq", "gemini"]


def test_keys_and_prompt_never_logged(both_keys, caplog):
    transport = FakeTransport({"gemini": (429, json.dumps({"error": {"message": "Quota exceeded"}})),
                               "groq": completion('{"ok": true}')})

    with caplog.at_level(logging.INFO, logger="interviews.llm"):
        ask(transport)

    logged = caplog.text
    assert "Quota exceeded" in logged
    assert "gemini-test-key" not in logged
    assert "groq-test-key" not in logged
    assert "Secret resume text" not in logged


def test_gemini_list_shaped_error_is_logged_readably(both_keys, caplog):
    body = json.dumps([{"error": {"code": 400, "message": "API key not valid."}}])
    transport = FakeTransport({"gemini": (400, body), "groq": completion('{"ok": true}')})

    with caplog.at_level(logging.WARNING, logger="interviews.llm"):
        ask(transport)

    assert "API key not valid." in caplog.text


@pytest.mark.parametrize("content", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}```',
    '  {"a": 1}  ',
])
def test_parse_json_reply_accepts_fenced_json(content):
    assert llm.parse_json_reply(content) == {"a": 1}
