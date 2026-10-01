"""
Speech to text for spoken answers, with Groq's Whisper.

WHY on the server: the browser's own speech recognition only works in
Chrome, Edge and Safari. Recording works in every browser, so the browser
records and Groq transcribes.
"""

import json
import logging
import time
import uuid

from django.conf import settings

from interviews import llm

logger = logging.getLogger(__name__)

TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
TIMEOUT_SECONDS = 30

# Groq picks the decoder from the file extension.
EXTENSIONS = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/aac": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def extension_for(content_type):
    """File extension for an upload's content type, or None if Whisper can't read it."""
    base = (content_type or "").split(";")[0].strip().lower()
    return EXTENSIONS.get(base)


def _multipart(fields, filename, content_type, data):
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def transcribe(audio, content_type, prompt="", transport=None):
    """
    Text spoken in the recording. `prompt` is the question being answered:
    Whisper uses it as context, which helps with technical words.
    Raises llm.AIUnavailable.
    """
    if not settings.GROQ_API_KEY:
        logger.error("Transcription needs GROQ_API_KEY.")
        raise llm.AIUnavailable("No transcription provider is configured.")

    transport = transport or llm.http_post
    fields = {
        "model": settings.GROQ_TRANSCRIBE_MODEL,
        "language": "en",
        "response_format": "json",
        "temperature": "0",
    }
    if prompt:
        # Whisper only reads the last 224 tokens of the prompt.
        fields["prompt"] = prompt[:800]
    body, multipart_type = _multipart(fields, f"answer.{extension_for(content_type)}", content_type, audio)
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": multipart_type}

    started = time.monotonic()
    try:
        status, response = transport(TRANSCRIBE_URL, headers, body, TIMEOUT_SECONDS)
        if status != 200:
            raise llm.ProviderError(f"HTTP {status}: {llm.error_reason(response)}")
        text = json.loads(response)["text"]
        if not isinstance(text, str):
            raise llm.ProviderError("transcript is not text")
    except (llm.ProviderError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Transcription failed after %.1fs: %s", time.monotonic() - started, exc)
        raise llm.AIUnavailable("Transcription failed.") from exc

    logger.info("Transcribed %d bytes in %.1fs", len(audio), time.monotonic() - started)
    return text.strip()
