# CLAUDE.md

This repo follows **`AGENTS.md`** (same directory) — read it first. The canonical, agent-facing build
plan lives in **`docs/final-build-plan/`**; read its `README.md` before writing any code.

Key reminders for QueuePilot:
- 🔒 Locked docs (`01`, `02`, `03`, `05` in `docs/final-build-plan/`) must not be contradicted or
  relitigated without explicit user sign-off + a new `05-DECISIONS-LOCKED.md` entry.
- The learning layer is a **core graded requirement** — every 📚 task ships a concept doc + runnable
  script + self-quiz, logged in `docs/final-build-plan/LEARNING-LOG.md`.
- One feature branch + PR per slice; keep `main` presentable (repo goes public after Slice A).
- Verify honestly against the project's verification rubric before claiming "done".
