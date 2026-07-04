"""Chat (generative) LLM provider protocol and registry.

Mirrors the embedding registry (`app/providers/embeddings.py`): a `ChatModel` protocol so the
LangGraph nodes are decoupled from the provider, with Groq as the default and Gemini/OpenAI as
drop-ins selectable by `CHAT_PROVIDER`. See docs/final-build-plan/05-DECISIONS-LOCKED.md D12.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from google import genai
from google.genai import types as genai_types
from groq import Groq
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app.config import get_settings

_logger = logging.getLogger(__name__)


def _report_usage(input_tokens: int | None, output_tokens: int | None, model: str) -> None:
    """Attach token usage + model name to the current LangSmith run, if one is active.

    LangSmith computes per-run cost from a ``usage_metadata`` dict of shape
    ``{"input_tokens", "output_tokens", "total_tokens"}`` set on the run (see
    ``RunTree.set(usage_metadata=...)``). Bare ``@traceable`` does not auto-extract
    usage from raw provider SDK responses the way ``wrap_openai``/LangChain chat
    models do, so each provider call here reports it explicitly.

    We also stamp ``ls_model_name`` into the run metadata: LangSmith matches its
    per-model pricing table on that name to turn usage into a **cost**. Without it,
    tokens show but Cost stays blank (the run name ``GroqChat.complete`` isn't a
    model). The model still needs a matching entry in LangSmith → Settings → Model
    Pricing for custom models like ``llama-3.3-70b-versatile`` / ``gemini-2.5-flash``.

    This is pure tracing bookkeeping: any failure (no active run, missing/None
    usage fields, SDK shape drift) is swallowed so it can never break the LLM call.
    """
    if input_tokens is None or output_tokens is None:
        return
    try:
        run = get_current_run_tree()
        if run is None:
            return
        run.set(
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            metadata={"ls_model_name": model},
        )
    except Exception:
        _logger.debug("_report_usage: could not attach usage_metadata to run tree", exc_info=True)


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

    @traceable(run_type="llm", name="GroqChat.complete")
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
        usage = getattr(resp, "usage", None)
        _report_usage(
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            self.MODEL,
        )
        return resp.choices[0].message.content or ""

    @traceable(run_type="llm", name="GroqChat.complete_json")
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
        usage = getattr(resp, "usage", None)
        _report_usage(
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            self.MODEL,
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


class GeminiChat:
    """Gemini chat provider (default: ``gemini-2.5-flash``).

    Used both as a drop-in ``CHAT_PROVIDER=gemini`` option and directly by the eval
    package's LLM-as-judge (``eval/evaluators/judge.py``), which pins the judge model to
    Gemini regardless of ``CHAT_PROVIDER`` to avoid self-preference bias against Groq.
    The API key is accepted at construction and never logged.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client: genai.Client = genai.Client(api_key=api_key)
        self._model = model

    @traceable(run_type="llm", name="GeminiChat.complete")
    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        usage = getattr(resp, "usage_metadata", None)
        _report_usage(
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            self._model,
        )
        return resp.text or ""

    @traceable(run_type="llm", name="GeminiChat.complete_json")
    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        usage = getattr(resp, "usage_metadata", None)
        _report_usage(
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            self._model,
        )
        content = resp.text or "{}"
        try:
            parsed: Any = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"GeminiChat.complete_json: model returned invalid JSON: {content[:200]}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ValueError(
                f"GeminiChat.complete_json: expected a JSON object, got {type(parsed).__name__}"
            )
        return parsed


#: Registry of chat providers (name → builder class). Add OpenAI here as another drop-in.
_PROVIDERS: dict[str, type[GroqChat] | type[GeminiChat]] = {"groq": GroqChat, "gemini": GeminiChat}
_PROVIDER_KEY_ATTRS: dict[str, str] = {"groq": "groq_api_key", "gemini": "gemini_api_key"}


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
