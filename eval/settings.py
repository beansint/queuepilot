"""Evaluation configuration.

Mirrors ``app/config.py``'s pydantic-settings style: env-driven, cached, extra env vars
ignored. Kept separate from ``app.config.Settings`` because eval knobs (judge model,
dataset name/version, sample size, recall-k) are never read by the request path.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalSettings(BaseSettings):
    """Evaluation settings loaded from environment / .env.

    - ``judge_provider`` / ``judge_model``: the LLM-as-judge (D6) is pinned to a
      different model than the chat model under test, to avoid self-preference bias.
    - ``dataset_name`` / ``dataset_version``: identify the LangSmith dataset (D2/D3).
    - ``sample_size``: number of held-out rows to sample into the eval dataset (D2).
    - ``recall_k``: ``k`` used by the label-recall@k evaluator (D4).
    - ``seed``: fixed seed for reproducible stratified sampling (D2).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    judge_provider: str = "gemini"
    judge_model: str = "gemini-2.5-flash"
    dataset_name: str = "queuepilot-eval"
    dataset_version: str = "v1"
    sample_size: int = 160
    recall_k: int = 5
    seed: int = 13


@lru_cache
def get_eval_settings() -> EvalSettings:
    """Return a cached ``EvalSettings`` instance."""
    return EvalSettings()
