"""learn/13_containerization.py — read the REAL Dockerfile + .dockerignore and prove
the containerization concepts (Slice E, E1–E3).

Run standalone:  uv run python learn/13_containerization.py

Companion doc: docs/learn/13-containerization.md

Fully offline — needs no Docker daemon. It parses the repo's actual ``Dockerfile`` and
``.dockerignore``, prints an annotated, teaching breakdown, and ASSERTS the properties that
make the image correct and safe: genuinely multi-stage, binds ``0.0.0.0``, respects ``$PORT``,
installs deps before copying source (layer caching), and keeps ``.env`` out of the build context.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_ROOT = Path(__file__).resolve().parent.parent
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"

# Plain-language gloss for the Dockerfile instructions we use.
_ANNOTATIONS: dict[str, str] = {
    "FROM": "start a build stage from a base image (multiple FROMs = multi-stage)",
    "WORKDIR": "set the working directory for later instructions",
    "COPY": "copy files into the image (a new layer); --from=<stage> pulls from an earlier stage",
    "RUN": "execute a build command, producing a cached layer",
    "ENV": "set an environment variable baked into the image",
    "EXPOSE": "document the port the app listens on (does not publish it)",
    "CMD": "the default process to run when the container starts",
}


def _lines() -> list[str]:
    return [ln.rstrip() for ln in _DOCKERFILE.read_text().splitlines()]


def _annotate() -> None:
    print("== Annotated Dockerfile ==\n")
    stage_no = 0
    for ln in _lines():
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue
        instr = stripped.split(maxsplit=1)[0].upper()
        note = _ANNOTATIONS.get(instr, "")
        if instr == "FROM":
            stage_no += 1
            print(f"\n  [stage {stage_no}] {stripped}")
            print(f"           └─ {note}")
        else:
            print(f"    {stripped}")
            if note:
                print(f"        └─ {note}")


def _checks() -> list[tuple[str, bool]]:
    df = _DOCKERFILE.read_text()
    di = _DOCKERIGNORE.read_text()
    from_count = sum(1 for ln in _lines() if ln.strip().upper().startswith("FROM "))
    return [
        ("Multi-stage build (>= 2 FROM stages)", from_count >= 2),
        ("Copies built dist from the frontend stage (COPY --from=frontend)",
         "--from=frontend" in df),
        ("Installs deps before copying app/ (layer caching)",
         df.find("uv sync") < df.find("COPY app/")),
        ("Binds 0.0.0.0 (reachable outside the container)", "0.0.0.0" in df),
        ("Respects the platform $PORT", "${PORT}" in df or "$PORT" in df),
        (".env excluded from the build context (no secret in image)",
         any(line.strip() == ".env" for line in di.splitlines())),
        ("Raw corpus (data/raw) excluded from context", "data/raw" in di),
    ]


def main() -> None:
    print("== Containerization: proving the QueuePilot image is correct & safe ==\n")
    if not _DOCKERFILE.is_file() or not _DOCKERIGNORE.is_file():
        raise SystemExit("Dockerfile or .dockerignore not found at repo root.")

    _annotate()

    print("\n== Property checks ==\n")
    results = _checks()
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'} {label}")

    failed = [label for label, ok in results if not ok]
    if failed:
        raise SystemExit(f"\n{len(failed)} containerization check(s) failed: {failed}")

    print(
        "\nTakeaway: one multi-stage image builds the React bundle in a throwaway Node stage, "
        "ships a lean\nPython runtime, caches by copying manifests before source, binds 0.0.0.0, "
        "respects $PORT, and\nnever bakes .env into a layer — so it runs the same locally and on "
        "Render."
    )


if __name__ == "__main__":
    main()
