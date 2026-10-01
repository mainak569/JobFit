import json
import logging

import pytest

from interviews import llm, speech


@pytest.fixture
def groq_key(settings):
    settings.GROQ_API_KEY = "groq-test-key"
    settings.GROQ_TRANSCRIBE_MODEL = "whisper-test"
    return settings


class FakeTransport:
    def __init__(self, status=200, body=json.dumps({"text": "  I used React hooks. "})):
        self.status = status
        self.body = body
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        return self.status, self.body


def test_transcribe_sends_audio_model_and_question(groq_key):
    transport = FakeTransport()

    text = speech.transcribe(b"AUDIO-BYTES", "audio/webm;codecs=opus", prompt="How do you use React?", transport=transport)

    assert text == "I used React hooks."
    call = transport.calls[0]
    assert call["url"] == speech.TRANSCRIBE_URL
    assert call["headers"]["Authorization"] == "Bearer groq-test-key"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    body = call["body"]
    assert b"AUDIO-BYTES" in body
    assert b'filename="answer.webm"' in body
    assert b"whisper-test" in body
    assert b"How do you use React?" in body


def test_transcribe_without_groq_key_is_unavailable(settings):
    transport = FakeTransport()

    with pytest.raises(llm.AIUnavailable):
        speech.transcribe(b"x", "audio/webm", transport=transport)
    assert transport.calls == []


@pytest.mark.parametrize("status, body", [
    (429, json.dumps({"error": {"message": "Rate limit reached"}})),
    (200, "not json"),
    (200, json.dumps({"no": "text"})),
])
def test_transcribe_failures_are_unavailable(groq_key, status, body, caplog):
    with caplog.at_level(logging.WARNING, logger="interviews.speech"):
        with pytest.raises(llm.AIUnavailable):
            speech.transcribe(b"x", "audio/webm", transport=FakeTransport(status, body))
    assert "groq-test-key" not in caplog.text


@pytest.mark.parametrize("content_type, extension", [
    ("audio/webm;codecs=opus", "webm"),
    ("audio/mp4", "mp4"),
    ("audio/ogg; codecs=opus", "ogg"),
    ("AUDIO/MPEG", "mp3"),
    ("application/pdf", None),
    ("", None),
])
def test_extension_for(content_type, extension):
    assert speech.extension_for(content_type) == extension
