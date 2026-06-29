# Build Plan — Slices B–E (Epic Outlines)

These are intentionally lightweight. Each becomes one **epic/tracking issue** now and gets a full
`docs/build-plans/slice-X.md` + task breakdown when started — its shape depends on results from the
prior slice. Design reference: `docs/superpowers/specs/2026-06-29-queuepilot-roadmap.md`.

---

## Slice B — Agentic Workflow (Milestone M-B)
Replace `app/analyze/baseline.py` with a **LangGraph** state machine behind the same `/analyze`
contract.
- Graph nodes: classify → retrieve → assess-missing-info → score → decide (answer/clarify/escalate)
  → draft grounded reply.
- Adds to the envelope: sentiment (frustration + negativity), SLA risk, escalation decision,
  clarification questions, suggested reply.
- Extends confidence v0 into the full blended score (adds classification certainty, route/priority
  consistency, missing-info + escalation-risk penalties).
- Uses the swappable LLM provider registry; OpenAI provable as a drop-in.
- 📚 Learning: LangGraph state & transitions, guarded-copilot pattern.
- **Closes job gaps:** LangGraph, LLM agent orchestration.

## Slice C — Dashboard + Observability (Milestone M-C)
- Single-page operations console: ticket input → result cards → suggested reply → similar-ticket
  evidence → trace summary.
- **Opt-out `--explain` debug mode**: node-by-node *why*, retrieval scores, confidence breakdown,
  live trace. Never forced into the normal path.
- **LangSmith** tracing wired into every run.
- 📚 Learning: tracing, in-app explainability.
- **Closes job gaps:** LangSmith (tracing), basic frontend.

## Slice D — Evaluation (Milestone M-D)
- LangSmith **offline** curated-dataset eval + **online** eval on real traces.
- Experiment comparison; human-feedback path; eval snapshot cards in the dashboard.
- 📚 Learning: offline vs online eval, building an eval dataset.
- **Closes job gaps:** LangSmith eval/experiments.

## Slice E — Deploy & Harden (Milestone M-E)
- Dockerize FastAPI; deploy to Render (same app serves UI + API).
- Invite-code access (signed HTTP-only cookie), rate limiting on `/analyze`, max input limits,
  request logging.
- **Closes job gaps:** cloud/deployment story.

---

## Deferred (not in v1)
GraphQL · Azure / Azure Service Bus · OpenAI-only · voice (ASR/TTS) · full auth · multi-tenant.
Framed as transferable in interviews.
