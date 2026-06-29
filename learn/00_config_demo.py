"""learn/00_config_demo.py — A1: typed, centralized, cached config (pydantic-settings).

Companion to docs/learn/00-tooling-and-skeleton.md. Run:

    uv run python learn/00_config_demo.py

Proves: settings are typed, secrets are redacted, and get_settings() returns a cached singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings  # noqa: E402

# Field names that hold secrets — we show whether they're set, never the value.
SECRET_FIELDS = {"gemini_api_key", "pinecone_api_key", "openai_api_key", "groq_api_key"}


def redacted(settings: Settings) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in settings.__class__.model_fields:
        value = getattr(settings, name)
        if name in SECRET_FIELDS:
            out[name] = "<set>" if value else "<unset>"
        else:
            out[name] = value
    return out


def main() -> None:
    print("== A1: typed config via pydantic-settings ==\n")

    settings = get_settings()
    print("Loaded settings (secrets redacted):")
    for key, value in redacted(settings).items():
        print(f"  {key:18} = {value!r}")

    print("\nTypes are enforced, not strings:")
    mic, alpha = settings.max_input_chars, settings.hybrid_alpha
    print(f"  max_input_chars -> {type(mic).__name__} = {mic}")
    print(f"  hybrid_alpha    -> {type(alpha).__name__} = {alpha}")

    print("\nget_settings() is cached (same object each call):")
    print(f"  get_settings() is get_settings()  ->  {get_settings() is get_settings()}")


if __name__ == "__main__":
    main()
