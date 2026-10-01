"""
LLM calls for the interviewer: Gemini first, Groq as fallback.

WHY no SDKs: both serve the OpenAI chat completions format, so one urllib
POST covers both.
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

PROVIDER_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}

# Two timeouts must fit inside gunicorn's 60s (render.yaml).
REQUEST_TIMEOUT_SECONDS = 20
TEMPERATURE = 0.4


class AIUnavailable(Exception):
    """No configured provider produced a usable reply."""


class ProviderError(Exception):
    """One provider failed; the next one may still succeed."""


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    api_key: str
    model: str


def configured_providers():
    """Providers in AI_PROVIDER_ORDER that have an API key, in that order."""
    providers = []
    for name in settings.AI_PROVIDER_ORDER:
        if name not in PROVIDER_URLS:
            logger.warning("Unknown AI provider %r in AI_PROVIDER_ORDER; skipping it.", name)
            continue
        api_key = getattr(settings, f"{name.upper()}_API_KEY", "")
        if not api_key:
            continue
        model = getattr(settings, f"{name.upper()}_MODEL")
        providers.append(Provider(name=name, url=PROVIDER_URLS[name], api_key=api_key, model=model))
    return providers


def http_post_json(url, headers, payload, timeout):
    """POST payload as JSON. Returns (status code, response body as text)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        # Groq's Cloudflare rejects urllib's default User-Agent (403, error 1010).
        headers={**headers, "Content-Type": "application/json", "User-Agent": "JobFit/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        raise ProviderError(f"request failed: {exc}") from exc


def _error_reason(body):
    try:
        error = json.loads(body)
        # Gemini wraps its error object in a list.
        if isinstance(error, list) and error:
            error = error[0]
        message = error["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = body
    return " ".join(str(message).split())[:200]


def parse_json_reply(content):
    """The JSON object in a reply. Some models still wrap it in a ```json fence."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise ProviderError("reply was not valid JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("reply was JSON but not an object")
    return value


def _ask(provider, messages, max_tokens, transport):
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {provider.api_key}"}
    status, body = transport(provider.url, headers, payload, REQUEST_TIMEOUT_SECONDS)
    if status != 200:
        raise ProviderError(f"HTTP {status}: {_error_reason(body)}")
    try:
        content = json.loads(body)["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError("unexpected response shape") from exc
    if not isinstance(content, str):
        raise ProviderError("reply had no text content")
    return parse_json_reply(content)


def chat_json(messages, *, purpose, max_tokens, validate=None, transport=None):
    """
    Return the reply as a dict, trying each provider in turn. A reply that
    fails `validate` counts as that provider failing. Raises AIUnavailable.
    """
    transport = transport or http_post_json
    providers = configured_providers()
    if not providers:
        logger.error("No AI provider is configured. Set GEMINI_API_KEY or GROQ_API_KEY.")
        raise AIUnavailable("No AI provider is configured.")

    for provider in providers:
        started = time.monotonic()
        try:
            reply = _ask(provider, messages, max_tokens, transport)
            if validate is not None:
                reply = validate(reply)
        except ProviderError as exc:
            # Never log the key or the prompt (it holds resume text).
            logger.warning(
                "AI %s call to %s (%s) failed after %.1fs: %s",
                purpose, provider.name, provider.model, time.monotonic() - started, exc,
            )
            continue
        logger.info(
            "AI %s call answered by %s (%s) in %.1fs",
            purpose, provider.name, provider.model, time.monotonic() - started,
        )
        return reply

    raise AIUnavailable("Every AI provider failed.")
