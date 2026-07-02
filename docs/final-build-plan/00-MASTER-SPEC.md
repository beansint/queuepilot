# 00 — Master Spec

## One sentence
QueuePilot is a semi-public, portfolio-first **agentic AI ticketing system** for IT/helpdesk: a user
submits a support ticket and the system classifies it, retrieves similar historical cases, predicts
routing/priority/risk, asks clarifying questions when needed, drafts a grounded suggested reply, and
logs the full run for evaluation.

## What it is / isn't
- **Is:** a lightweight internal support-operations console (single-page dashboard) backed by a
  guarded, inspectable workflow.
- **Isn't:** a generic chatbot. It produces operational outputs mapped to a dashboard, not free chat.

## Why it exists
A portfolio project demonstrating a production-style agentic AI workflow — LangGraph orchestration,
hybrid retrieval, LangSmith evaluation, agent orchestration, and clean API design — and a
**learning vehicle**. The learning layer is therefore a core graded requirement, not optional polish.

## Core outputs (per analyzed ticket)
- Category
- Queue recommendation
- Priority recommendation
- Sentiment signals: customer frustration + message negativity
- SLA risk (numeric)
- Overall confidence (numeric, blended — never raw LLM self-confidence)
- Escalation decision
- Clarification question(s) when needed
- Suggested reply (grounded in retrieved evidence)
- Supporting similar-ticket evidence

(Slice A populates a subset; later slices fill the rest behind the same API contract — see `03`.)

## System philosophy — guarded support copilot
- Clear ticket + strong retrieval → confident recommendations + strong suggested reply.
- Partially missing details → still useful tentative outputs, **lower confidence**, targeted
  clarification question.
- High uncertainty or operational risk → recommend **escalation** rather than feign certainty.

Help under uncertainty; never overcommit.

## Confidence approach
Blended numeric score from: retrieval quality, classification certainty, route/priority consistency,
missing-info penalties, escalation-risk penalties, optional low-weight LLM judgment. Explainable and
tunable for dashboards and debugging.

## Success criteria (by slice)
- **A:** `/analyze` returns category/queue/priority + hybrid-retrieved neighbors + confidence v0 on
  ~3k real tickets. No LangGraph.
- **B:** the same endpoint is driven by a LangGraph state machine producing the full output envelope.
- **C:** a single-page console + opt-out `--explain` debug mode + LangSmith tracing on every run.
- **D:** LangSmith offline + online eval, experiments, feedback path.
- **E:** Dockerized, deployed to Render, invite-code access + rate limiting.
- **F:** an additive `/graphql` endpoint (Strawberry) exposing `analyze` (query) + `submitFeedback`
  (mutation) at full parity with the REST envelope, gated + rate-limited like REST; GraphiQL enabled.

## Scope v1 / deferred
**In:** the six slices above (A–F). **Deferred (out of scope for v1):**
Azure / Azure Service Bus, OpenAI-only, voice (ASR/TTS), full auth/user management, multi-tenant SaaS.
(GraphQL was originally deferred; **un-deferred as additive Slice F** — see `05-DECISIONS-LOCKED.md` D17.)
