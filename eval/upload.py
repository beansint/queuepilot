"""Idempotent LangSmith dataset upload (D3).

Creates the dataset if absent, then adds only examples that are missing (keyed by a
hash of ``inputs["text"]``) so re-running the uploader after adding new fixtures never
duplicates existing examples.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from eval.client import get_langsmith_client
from eval.dataset import EvalExample, build_eval_dataset
from eval.settings import get_eval_settings

_logger = logging.getLogger(__name__)


def _text_hash(text: str) -> str:
    """Return a stable hash of an example's input text, used as a uniqueness key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _existing_text_hashes(client: Any, dataset_name: str) -> set[str]:
    """Return the set of input-text hashes already present in the named dataset."""
    hashes: set[str] = set()
    for example in client.list_examples(dataset_name=dataset_name):
        text = None
        inputs = getattr(example, "inputs", None)
        if isinstance(inputs, dict):
            text = inputs.get("text")
        if text:
            hashes.add(_text_hash(text))
    return hashes


def upload_dataset(
    examples: list[EvalExample],
    *,
    client: Any | None = None,
    name: str | None = None,
    version: str | None = None,
) -> str:
    """Create (if absent) a LangSmith dataset and upload only missing examples.

    Args:
        examples: Examples to ensure are present in the dataset (e.g. from
            ``build_eval_dataset()``).
        client: A ``langsmith.Client``. Defaults to ``get_langsmith_client()``.
        name: Dataset name. Defaults to ``EvalSettings.dataset_name``.
        version: Dataset version tag, folded into the description. Defaults to
            ``EvalSettings.dataset_version``.

    Returns:
        The dataset name (uploaded to, or just resolved when no client is available).
    """
    eval_settings = get_eval_settings()
    resolved_name = name if name is not None else eval_settings.dataset_name
    resolved_version = version if version is not None else eval_settings.dataset_version

    resolved_client = client if client is not None else get_langsmith_client()
    if resolved_client is None:
        _logger.warning(
            "upload_dataset: no LangSmith client available; skipping upload for %r "
            "(returning name only).",
            resolved_name,
        )
        return resolved_name

    if resolved_client.has_dataset(dataset_name=resolved_name):
        resolved_client.read_dataset(dataset_name=resolved_name)
    else:
        resolved_client.create_dataset(
            resolved_name,
            description=f"QueuePilot offline eval dataset ({resolved_version}).",
        )

    existing_hashes = _existing_text_hashes(resolved_client, resolved_name)

    to_add = [ex for ex in examples if _text_hash(ex.inputs.get("text", "")) not in existing_hashes]

    if to_add:
        resolved_client.create_examples(
            dataset_name=resolved_name,
            inputs=[ex.inputs for ex in to_add],
            outputs=[ex.outputs for ex in to_add],
        )
        _logger.info("upload_dataset: added %d new example(s) to %r.", len(to_add), resolved_name)
    else:
        _logger.info("upload_dataset: %r already up to date; nothing to add.", resolved_name)

    return resolved_name


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    built_examples = build_eval_dataset()
    uploaded_name = upload_dataset(built_examples)
    print(f"Dataset {uploaded_name!r}: ensured {len(built_examples)} example(s).")
