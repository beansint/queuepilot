# QueuePilot — Final Build Plan (canonical, agent-facing)

**This directory is the single source of truth for building QueuePilot.** If you are an agent or a
new contributor, read this before touching any code.

## Read order

1. `00-MASTER-SPEC.md` — what QueuePilot is, its outputs, and its philosophy.
2. `01-TECH-STACK-LOCKED.md` — the locked stack. 🔒
3. `05-DECISIONS-LOCKED.md` — decisions already made. **Do not relitigate these.** 🔒
4. `02-DATA-MODEL.md` — Pinecone index + normalized record shapes. 🔒
5. `03-API-CONTRACT.md` — the binding `/analyze` request/response contract. 🔒
6. `06-ARCHITECTURE.md` — module boundaries + data flow.
7. `04-BUILD-SEQUENCE.md` — what to build, in what order, mapped to issues.
8. `LEARNING-LOG.md` — the learning layer journal; update it as you build.

## Doc ownership (avoid drift)

| Topic | Authoritative doc | Nothing else may contradict it |
|---|---|---|
| Stack & versions | `01-TECH-STACK-LOCKED.md` | |
| Pinecone schema, record shape | `02-DATA-MODEL.md` | |
| API request/response | `03-API-CONTRACT.md` | |
| Task order & issue mapping | `04-BUILD-SEQUENCE.md` | |
| Why a decision was made | `05-DECISIONS-LOCKED.md` | |

Design *history* (the brainstorm narrative) lives in `../superpowers/specs/` and is immutable —
it records how we got here, not what is current. When current state changes, update THIS directory.

## Agent rules (non-negotiable)

1. **Respect 🔒 locked docs.** Changing anything in a locked doc requires explicit user sign-off and
   a new entry in `05-DECISIONS-LOCKED.md`.
2. **The API contract (`03`) and data model (`02`) are binding.** Code conforms to them, not the
   reverse. If you believe one is wrong, stop and raise it — don't silently diverge.
3. **The learning layer is a core graded requirement.** Every task tagged 📚 ships a concept doc +
   runnable script + self-quiz, and you log it in `LEARNING-LOG.md`. Skipping it = task not done.
4. **One feature branch + PR per slice.** Keep `main` presentable (repo goes public after Slice A).
5. **Verify honestly.** State what ran vs. what is N/A; never round "renders" up to "verified".

## Issue trackers

GitHub `beansint/queuepilot` and Linear project `QueuePilot` (team Devs) mirror each other 1:1.
Milestones = slices (M-A…M-E). See `04-BUILD-SEQUENCE.md` for the exact issue map.
