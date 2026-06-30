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
    voyage_api_key: str | None = None
    pinecone_api_key: str | None = None
    pinecone_index: str = "queuepilot"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Embedding provider registry (D11; default voyage, Gemini a drop-in)
    embedding_provider: str = "voyage"

    # Chat-LLM provider registry (Slice B; default Groq, Gemini/OpenAI drop-ins — D12)
    chat_provider: str = "groq"
    openai_api_key: str | None = None
    groq_api_key: str | None = None

    # --- Data ingest (Kaggle API; used by data/download.py, task A7) ---
    kaggle_username: str | None = None
    kaggle_key: str | None = None

    # --- Retrieval ---
    # Active provider dim: voyage-3.5-lite @ 1024 (D11); change triggers full re-index
    embed_dim: int = 1024
    corpus_cap: int = 3000
    hybrid_alpha: float = 0.5


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
