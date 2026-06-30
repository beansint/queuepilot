"""Download the Kaggle support-ticket dataset into data/raw/ (task A7).

Reproducible corpus fetch via kagglehub. Requires Kaggle API credentials — set KAGGLE_USERNAME and
KAGGLE_KEY in .env (see .env.example) or place ~/.kaggle/kaggle.json. Raw data is gitignored.

    uv run python data/download.py

Idempotent: re-running re-copies the latest cached CSV(s) into data/raw/.
See docs/final-build-plan/07-DATASET.md for provenance and licensing.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Standalone script: put the project root on sys.path so `import app` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402

DATASET = "tobiasbueck/multilingual-customer-support-tickets"
RAW_DIR = Path(__file__).resolve().parent / "raw"


def main() -> None:
    # Surface credentials from .env (pydantic-settings) into the env kagglehub reads.
    settings = get_settings()
    if settings.kaggle_username and settings.kaggle_key:
        os.environ.setdefault("KAGGLE_USERNAME", settings.kaggle_username)
        os.environ.setdefault("KAGGLE_KEY", settings.kaggle_key)

    if not (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")):
        sys.exit(
            "Kaggle credentials missing. Set KAGGLE_USERNAME and KAGGLE_KEY in .env "
            "(see .env.example) or add ~/.kaggle/kaggle.json. "
            "Token: https://www.kaggle.com/settings -> API -> Create New Token."
        )

    import kagglehub  # imported here so the script fails fast on creds, not import

    print(f"Downloading {DATASET} ...")
    source = Path(kagglehub.dataset_download(DATASET))
    csv_files = sorted(source.rglob("*.csv"))
    if not csv_files:
        sys.exit(f"No CSV files found under the downloaded dataset at {source}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for csv in csv_files:
        dest = RAW_DIR / csv.name
        shutil.copy2(csv, dest)
        print(f"  copied {csv.name}  ({dest.stat().st_size // 1024} KB)")

    print(f"Done. {len(csv_files)} CSV file(s) in {RAW_DIR}/")
    print("Next: inspect columns, then run the ingest pipeline (task A7).")


if __name__ == "__main__":
    main()
