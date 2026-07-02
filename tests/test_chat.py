"""B2 — offline unit tests for the ChatModel registry (Groq client is faked; no network)."""

from __future__ import annotations

from typing import Any

import pytest

import app.providers.chat as chat_mod
from app.config import Settings
from app.providers.chat import GeminiChat, GroqChat, get_chat_model


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(self._content)


class _FakeChatNamespace:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


def _fake_groq_factory(content: str) -> type:
    class FakeGroq:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat = _FakeChatNamespace(content)

    return FakeGroq


def test_complete_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory("hello there"))
    out = GroqChat(api_key="k").complete("be terse", "hi")
    assert out == "hello there"


def test_complete_uses_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory("x"))
    model = GroqChat(api_key="k")
    model.complete("s", "u")
    calls = model._client.chat.completions.calls  # type: ignore[attr-defined]
    assert calls[0]["model"] == GroqChat.MODEL


def test_complete_json_parses_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory('{"queue": "IT", "n": 3}'))
    out = GroqChat(api_key="k").complete_json("s", "u")
    assert out == {"queue": "IT", "n": 3}


def test_complete_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory("not json"))
    with pytest.raises(ValueError, match="invalid JSON"):
        GroqChat(api_key="k").complete_json("s", "u")


def test_complete_json_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory("[1, 2, 3]"))
    with pytest.raises(ValueError, match="expected a JSON object"):
        GroqChat(api_key="k").complete_json("s", "u")


def test_registry_resolves_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "Groq", _fake_groq_factory("x"))
    monkeypatch.setattr(
        chat_mod, "get_settings", lambda: Settings(chat_provider="groq", groq_api_key="k")
    )
    assert isinstance(get_chat_model(), GroqChat)


def test_registry_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "get_settings", lambda: Settings(chat_provider="nope"))
    with pytest.raises(ValueError, match="Unknown CHAT_PROVIDER"):
        get_chat_model()


def test_registry_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        chat_mod, "get_settings", lambda: Settings(chat_provider="groq", groq_api_key=None)
    )
    with pytest.raises(RuntimeError, match="API key is not set"):
        get_chat_model()


# ---------------------------------------------------------------------------
# GeminiChat (D6 — used both as a CHAT_PROVIDER drop-in and by the eval judge)
# ---------------------------------------------------------------------------


class _FakeGenaiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> _FakeGenaiResponse:
        self.calls.append(kwargs)
        return _FakeGenaiResponse(self._text)


def _fake_genai_client_factory(text: str) -> type:
    class FakeGenaiClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.models = _FakeModels(text)

    return FakeGenaiClient


def test_gemini_complete_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory("hi there"))
    out = GeminiChat(api_key="k").complete("be terse", "hi")
    assert out == "hi there"


def test_gemini_complete_uses_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory("x"))
    model = GeminiChat(api_key="k", model="gemini-2.5-flash")
    model.complete("s", "u")
    calls = model._client.models.calls  # type: ignore[attr-defined]
    assert calls[0]["model"] == "gemini-2.5-flash"


def test_gemini_complete_json_forces_json_mime_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory('{"a": 1}'))
    model = GeminiChat(api_key="k")
    out = model.complete_json("s", "u")
    assert out == {"a": 1}
    calls = model._client.models.calls  # type: ignore[attr-defined]
    assert calls[0]["config"].response_mime_type == "application/json"


def test_gemini_complete_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory("not json"))
    with pytest.raises(ValueError, match="invalid JSON"):
        GeminiChat(api_key="k").complete_json("s", "u")


def test_gemini_complete_json_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory("[1, 2, 3]"))
    with pytest.raises(ValueError, match="expected a JSON object"):
        GeminiChat(api_key="k").complete_json("s", "u")


def test_registry_resolves_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod.genai, "Client", _fake_genai_client_factory("x"))
    monkeypatch.setattr(
        chat_mod, "get_settings", lambda: Settings(chat_provider="gemini", gemini_api_key="k")
    )
    assert isinstance(get_chat_model(), GeminiChat)
