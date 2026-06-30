"""Chat (generative) LLM provider protocol and registry.

Mirrors the embedding registry (`app/providers/embeddings.py`): a `ChatModel` protocol so the
LangGraph nodes are decoupled from the provider, with Groq as the default and Gemini/OpenAI as
drop-ins selectable by `CHAT_PROVIDER`. See docs/final-build-plan/05-DECISIONS-LOCKED.md D12.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from groq import Groq

from app.config import get_settings


class ChatModel(Protocol):
    """Structural protocol for chat/generative providers used by the workflow nodes."""

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        """Return the model's text completion for a system + user prompt."""
        ...

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        """Return the model's completion parsed as a JSON object (dict)."""
        ...


class GroqChat:
    """Groq chat provider (default: ``llama-3.3-70b-versatile``).

    The API key is accepted at construction and never logged. ``complete_json`` uses Groq's
    JSON response mode so the workflow's classification/sentiment nodes get structured output.
    """

    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str) -> None:
        self._client = Groq(api_key=api_key)

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        resp = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        try:
            parsed: Any = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"GroqChat.complete_json: model returned invalid JSON: {content[:200]}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ValueError(
                f"GroqChat.complete_json: expected a JSON object, got {type(parsed).__name__}"
            )
        return parsed


#: Registry of chat providers (name → builder class). Add Gemini/OpenAI here as drop-ins.
_PROVIDERS: dict[str, type[GroqChat]] = {"groq": GroqChat}
_PROVIDER_KEY_ATTRS: dict[str, str] = {"groq": "groq_api_key"}


def get_chat_model() -> ChatModel:
    """Build the configured `ChatModel` from settings (`CHAT_PROVIDER`).

    Raises:
        ValueError: if `CHAT_PROVIDER` names an unknown provider.
        RuntimeError: if the matching API key is missing.
    """
    settings = get_settings()
    provider = settings.chat_provider
    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unknown CHAT_PROVIDER {provider!r}. Known: {sorted(_PROVIDERS)}."
        )
    key = getattr(settings, _PROVIDER_KEY_ATTRS[provider])
    if not key:
        raise RuntimeError(
            f"Chat provider {provider!r} selected but its API key is not set. See .env.example."
        )
    return _PROVIDERS[provider](api_key=key)
