"""Application configuration.

All settings are environment-driven via pydantic-settings. Provider keys stay server-side;
never log or return them. See docs/final-build-plan/01-TECH-STACK-LOCKED.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration loaded from environment / .env.

    Keys are stubbed in Slice A and consumed by later tasks:
    - Gemini / Pinecone keys: A3, A5, A7
    - HYBRID_ALPHA: A6
    - CORPUS_CAP: A7
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "QueuePilot"
    environment: str = "development"
    max_input_chars: int = 8000

    # --- Providers (server-side only; required from A3 onward) ---
    gemini_api_key: str | None = None
    pinecone_api_key: str | None = None
    pinecone_index: str = "queuepilot"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Optional chat-LLM provider registry keys (used from Slice B)
    openai_api_key: str | None = None
    groq_api_key: str | None = None

    # --- Retrieval ---
    embed_dim: int = 768  # Pinned at A3: gemini-embedding-001, Matryoshka 768-dim
    corpus_cap: int = 3000
    hybrid_alpha: float = 0.5


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
