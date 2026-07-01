"""LangGraph workflow for Slice B (full guarded-copilot graph).

Replaces the Slice A `Analyzer` with a `StateGraph` behind the same `/analyze` contract. State
(`TicketState`) threads through nodes; each node returns a partial-state dict that LangGraph merges.

Slice B build order (08-SLICE-B-DESIGN.md):
  B1  — scaffold + ``retrieve`` node.
  B3  — ``classify`` node (LLM picks category/queue/priority from neighbors).
  B5  — ``assess_missing`` node (LLM lists missing ticket details).
  B6  — ``sentiment`` node (LLM scores frustration + negativity).
  B7  — ``score`` node (deterministic: full_confidence + sla_risk).
  B8  — ``decide`` node + conditional routing (guarded-copilot pattern).
  B9  — ``draft_reply`` and ``clarify`` generation nodes (LLM, degrade gracefully).

Current graph:
  START → retrieve → classify → sentiment → assess_missing → score → decide ◇
                                                        ├ answer   → draft_reply → END
                                                        ├ clarify  → clarify     → END
                                                        └ escalate → END
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from app.analyze.baseline import majority_vote
from app.analyze.scoring import full_confidence_breakdown, sla_risk_breakdown
from app.config import get_settings
from app.providers.chat import ChatModel
from app.providers.embeddings import Embedder
from app.retrieval.hybrid import hybrid_score_norm
from app.retrieval.pinecone_store import Neighbor, PineconeStore
from app.retrieval.sparse import BM25SparseEncoder

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM system-prompt constants (module-level for readability + testability)
# ---------------------------------------------------------------------------

CLASSIFY_SYSTEM: str = (
    "You are a support ticket classifier. "
    "Given a ticket and a list of similar historical tickets (with their labels), "
    "choose the best category, queue, and priority for the new ticket. "
    "Return ONLY a JSON object with three keys: "
    '"category" (string or null), "queue" (string or null), "priority" (string or null). '
    "Use the similar tickets as strong label hints. Return null for any field you cannot determine."
)

SENTIMENT_SYSTEM: str = (
    "You are a sentiment analyzer for support tickets. "
    "Assess the emotional tone of the ticket text. "
    "Return ONLY a JSON object with two keys: "
    '"frustration" (float 0.0–1.0, where 0 = calm and 1 = extremely frustrated) and '
    '"negativity" (float 0.0–1.0, where 0 = neutral/positive and 1 = highly negative). '
    "Base the scores on word choice, punctuation, capitalization, and context."
)

ASSESS_MISSING_SYSTEM: str = (
    "You are a support quality reviewer. "
    "Identify important information that is missing from the ticket "
    "but would help resolve it faster. "
    'Return ONLY a JSON object with one key: "missing_info" '
    "(list of short strings, each describing a missing detail, "
    "e.g. 'no error message', 'no account id', 'no steps to reproduce'). "
    "Return an empty list if the ticket contains all necessary information."
)

DRAFT_REPLY_SYSTEM: str = (
    "You are a helpful support agent. "
    "Using the provided ticket and similar historical cases as evidence, "
    "write a concise, grounded response to the customer. "
    "Be professional and helpful. "
    "Base your answer on the historical cases provided — do NOT speculate beyond them."
)

CLARIFY_SYSTEM: str = (
    "You are a support intake agent. "
    "Given a ticket and a list of missing details, "
    "write 1–2 short, polite clarifying questions to gather the needed information. "
    'Return ONLY a JSON object with one key: "clarification" '
    "(a list of 1–2 question strings)."
)

# ---------------------------------------------------------------------------
# Decision thresholds (module constants — importable for testing and learning scripts)
# ---------------------------------------------------------------------------

#: At or above this confidence, answer directly — strong retrieval/agreement is trusted, so we don't
#: over-clarify on the LLM's eager missing-info nor escalate on a high-but-confident SLA risk.
CLARIFY_CONFIDENCE_BELOW: float = 0.7

#: Below this confidence the copilot is genuinely uncertain → escalate to a human.
ESCALATE_CONFIDENCE_BELOW: float = 0.4

#: Escalate when SLA risk is extreme AND we are not already confident (see route_decision).
ESCALATE_SLA_RISK_ABOVE: float = 0.85


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TicketState(TypedDict, total=False):
    """State threaded through the workflow (see 08-SLICE-B-DESIGN.md).

    ``total=False`` so nodes populate fields incrementally; only ``text`` is seeded at invoke time.
    """

    text: str
    neighbors: list[Neighbor]
    category: str | None
    queue: str | None
    priority: str | None
    sentiment: dict[str, float] | None
    missing_info: list[str]
    sla_risk: float | None
    confidence: float
    decision: str
    clarification: list[str]
    suggested_reply: str | None
    escalate: bool

    # --- --explain accumulator (Slice C, C4) — in-app only, never reconstructed
    # from LangSmith. ``reasoning`` is merged by each LLM node (LangGraph overwrites
    # by key, so each node reads the existing dict and returns the merged copy).
    reasoning: dict[str, str]
    confidence_breakdown: dict[str, Any]
    sla_breakdown: dict[str, Any]


# ---------------------------------------------------------------------------
# Pure routing helper (importable without instantiating the graph)
# ---------------------------------------------------------------------------


def route_decision(
    confidence: float,
    sla_risk_score: float,
    missing_info: list[str],
) -> str:
    """Return the routing decision for a ticket given its scored state.

    Confidence-primary routing (a guarded copilot that doesn't overcommit OR over-escalate):
      1. Confident (>= CLARIFY_CONFIDENCE_BELOW) → **answer** directly. Strong retrieval + label
         agreement is trusted, so we don't escalate on a high-but-confident SLA risk nor clarify on
         the LLM's (typically eager) missing-info list.
      2. Otherwise, if genuinely uncertain (confidence < ESCALATE_CONFIDENCE_BELOW) or the SLA risk
         is extreme (> ESCALATE_SLA_RISK_ABOVE) → **escalate** to a human.
      3. Otherwise, if details are missing → **clarify** with the customer.
      4. Else → **answer**.

    Args:
        confidence:     Blended confidence score from ``full_confidence`` (in [0, 1]).
        sla_risk_score: SLA risk score from ``sla_risk`` (in [0, 1]).
        missing_info:   List of missing detail strings from ``assess_missing``.

    Returns:
        One of ``"escalate"``, ``"clarify"``, or ``"answer"``.
    """
    if confidence >= CLARIFY_CONFIDENCE_BELOW:
        return "answer"
    if confidence < ESCALATE_CONFIDENCE_BELOW or sla_risk_score > ESCALATE_SLA_RISK_ABOVE:
        return "escalate"
    if missing_info:
        return "clarify"
    return "answer"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(
    embedder: Embedder,
    sparse_encoder: BM25SparseEncoder,
    store: PineconeStore,
    chat_model: ChatModel,
    *,
    top_k: int = 5,
    alpha: float | None = None,
) -> Any:
    """Build and compile the workflow graph from injected dependencies.

    All dependencies are injected so the graph is testable with fakes (no network).
    Each LLM node degrades gracefully — a node failure never raises through the graph.
    """
    effective_alpha = alpha if alpha is not None else get_settings().hybrid_alpha

    def _with_reasoning(state: TicketState, node: str, rationale: str) -> dict[str, str]:
        """Merge a node's rationale into the ``reasoning`` accumulator (--explain, C4).

        LangGraph overwrites state by key, so each node reads the existing dict off
        state and returns the merged copy rather than a bare ``{node: rationale}``.
        """
        reasoning = dict(state.get("reasoning") or {})
        reasoning[node] = rationale
        return reasoning

    # ------------------------------------------------------------------
    # Node: retrieve (Slice A hybrid retrieval — no LLM)
    # ------------------------------------------------------------------

    def retrieve(state: TicketState) -> dict[str, Any]:
        """Hybrid-retrieve neighbors for the ticket text (reuses Slice A retrieval)."""
        text = state["text"]
        dense = embedder.embed_query(text)
        sparse = sparse_encoder.encode_query(text)
        weighted_dense, weighted_sparse = hybrid_score_norm(dense, sparse, effective_alpha)
        neighbors = store.hybrid_query(weighted_dense, weighted_sparse, top_k=top_k)
        return {"neighbors": neighbors}

    # ------------------------------------------------------------------
    # Node: classify (B3) — LLM picks category/queue/priority
    # ------------------------------------------------------------------

    def classify(state: TicketState) -> dict[str, Any]:
        """LLM-classify the ticket's category, queue, and priority using neighbor hints.

        Falls back to ``majority_vote`` when the LLM call fails so the graph never stalls.
        """
        text: str = state["text"]
        neighbors: list[Neighbor] = cast(list[Neighbor], state.get("neighbors") or [])

        try:
            hints = "\n".join(
                f"- queue={n.queue!r}  priority={n.priority!r}  type={n.type!r}"
                f"  (score={n.score:.2f})"
                for n in neighbors
            )
            user = f"Ticket:\n{text}\n\nSimilar tickets:\n{hints or '(none retrieved)'}"
            result = chat_model.complete_json(CLASSIFY_SYSTEM, user)
            rationale = (
                f"LLM classified category={result.get('category')!r} "
                f"queue={result.get('queue')!r} priority={result.get('priority')!r} "
                f"from {len(neighbors)} retrieved neighbor(s)."
            )
            return {
                "category": result.get("category"),
                "queue": result.get("queue"),
                "priority": result.get("priority"),
                "reasoning": _with_reasoning(state, "classify", rationale),
            }
        except Exception:
            _logger.exception("classify node: LLM call failed; falling back to majority_vote")
            fb_queue, fb_priority, fb_category, _ = majority_vote(neighbors)
            rationale = (
                "LLM call failed; fell back to majority_vote over retrieved neighbors "
                f"(queue={fb_queue!r})."
            )
            return {
                "category": fb_category,
                "queue": fb_queue,
                "priority": fb_priority,
                "reasoning": _with_reasoning(state, "classify", rationale),
            }

    # ------------------------------------------------------------------
    # Node: sentiment (B6) — LLM scores frustration + negativity
    # ------------------------------------------------------------------

    def sentiment(state: TicketState) -> dict[str, Any]:
        """LLM-score the ticket's emotional tone (frustration and negativity in [0, 1]).

        Falls back to ``{"sentiment": None}`` on any error so downstream nodes see a safe value.
        """
        text: str = state["text"]
        try:
            result = chat_model.complete_json(SENTIMENT_SYSTEM, text)
            frustration = float(result.get("frustration", 0.0))
            negativity = float(result.get("negativity", 0.0))
            # Clamp both scores to [0, 1] in case the model returns out-of-range values.
            frustration = max(0.0, min(1.0, frustration))
            negativity = max(0.0, min(1.0, negativity))
            rationale = f"LLM scored frustration={frustration:.2f} negativity={negativity:.2f}."
            return {
                "sentiment": {"frustration": frustration, "negativity": negativity},
                "reasoning": _with_reasoning(state, "sentiment", rationale),
            }
        except Exception:
            _logger.exception("sentiment node: LLM call failed; returning None")
            return {
                "sentiment": None,
                "reasoning": _with_reasoning(
                    state, "sentiment", "LLM call failed; sentiment=None."
                ),
            }

    # ------------------------------------------------------------------
    # Node: assess_missing (B5) — LLM lists missing ticket details
    # ------------------------------------------------------------------

    def assess_missing(state: TicketState) -> dict[str, Any]:
        """LLM-identify important missing information in the ticket text.

        Falls back to an empty list on any error so downstream nodes always see a list.
        """
        text: str = state["text"]
        try:
            result = chat_model.complete_json(ASSESS_MISSING_SYSTEM, text)
            raw = result.get("missing_info", [])
            if not isinstance(raw, list):
                return {
                    "missing_info": [],
                    "reasoning": _with_reasoning(
                        state, "assess_missing", "LLM returned non-list missing_info; using []."
                    ),
                }
            missing: list[str] = [str(item) for item in raw if isinstance(item, str)]
            rationale = f"LLM flagged {len(missing)} missing detail(s): {missing}."
            return {
                "missing_info": missing,
                "reasoning": _with_reasoning(state, "assess_missing", rationale),
            }
        except Exception:
            _logger.exception("assess_missing node: LLM call failed; returning empty list")
            return {
                "missing_info": [],
                "reasoning": _with_reasoning(
                    state, "assess_missing", "LLM call failed; missing_info=[]."
                ),
            }

    # ------------------------------------------------------------------
    # Node: score (B7) — deterministic confidence + SLA risk, no LLM
    # ------------------------------------------------------------------

    def score(state: TicketState) -> dict[str, Any]:
        """Compute full blended confidence and SLA risk from the current state.

        Deterministic — no LLM, no try/except needed. Reads neighbors (for
        re-deriving agreement and majority_queue), state labels from classify,
        sentiment from the sentiment node, and missing_info length.
        """
        neighbors: list[Neighbor] = cast(list[Neighbor], state.get("neighbors") or [])
        maj_queue, _, _, agreement = majority_vote(neighbors)
        top_score: float = neighbors[0].score if neighbors else 0.0
        llm_queue: str | None = state.get("queue")
        missing_count = len(state.get("missing_info") or [])

        sentiment_data: dict[str, float] | None = state.get("sentiment")
        frustration: float = (sentiment_data or {}).get("frustration", 0.0)
        priority: str | None = state.get("priority")
        has_missing = missing_count > 0

        conf_breakdown = full_confidence_breakdown(
            top_score, agreement, llm_queue, maj_queue, missing_count
        )
        risk_breakdown = sla_risk_breakdown(priority, frustration, has_missing)
        conf = conf_breakdown["final"]
        risk = risk_breakdown["final"]
        rationale = f"confidence={conf:.3f} sla_risk={risk:.3f} (see confidence/sla breakdowns)."
        return {
            "confidence": conf,
            "sla_risk": risk,
            "confidence_breakdown": conf_breakdown,
            "sla_breakdown": risk_breakdown,
            "reasoning": _with_reasoning(state, "score", rationale),
        }

    # ------------------------------------------------------------------
    # Node: decide (B8) — conditional routing (guarded copilot)
    # ------------------------------------------------------------------

    def decide(state: TicketState) -> dict[str, Any]:
        """Choose answer / clarify / escalate from scored state (no I/O)."""
        conf = float(state.get("confidence", 0.0))
        risk = float(state.get("sla_risk") or 0.0)
        missing: list[str] = list(state.get("missing_info") or [])
        decision = route_decision(conf, risk, missing)
        return {"decision": decision, "escalate": decision == "escalate"}

    def router(state: TicketState) -> str:
        """Extract the routing key from state for ``add_conditional_edges``."""
        return state.get("decision", "escalate")

    # ------------------------------------------------------------------
    # Node: draft_reply (B9) — LLM drafts a grounded reply (answer branch)
    # ------------------------------------------------------------------

    def draft_reply(state: TicketState) -> dict[str, Any]:
        """LLM-generate a suggested reply grounded in the top neighbor snippets.

        Falls back to ``{"suggested_reply": None}`` on any error.
        """
        text: str = state["text"]
        neighbors: list[Neighbor] = cast(list[Neighbor], state.get("neighbors") or [])
        try:
            snippets = "\n".join(
                f"- [{n.queue}/{n.priority}] {n.snippet}"
                for n in neighbors[:3]
            )
            user = f"Ticket:\n{text}\n\nSimilar resolved cases:\n{snippets or '(none)'}"
            reply = chat_model.complete(DRAFT_REPLY_SYSTEM, user)
            rationale = f"LLM drafted a reply grounded in top {min(3, len(neighbors))} neighbor(s)."
            return {
                "suggested_reply": reply,
                "reasoning": _with_reasoning(state, "draft_reply", rationale),
            }
        except Exception:
            _logger.exception("draft_reply node: LLM call failed; returning None")
            return {
                "suggested_reply": None,
                "reasoning": _with_reasoning(
                    state, "draft_reply", "LLM call failed; suggested_reply=None."
                ),
            }

    # ------------------------------------------------------------------
    # Node: clarify (B9) — LLM generates clarifying questions (clarify branch)
    # ------------------------------------------------------------------

    def clarify(state: TicketState) -> dict[str, Any]:
        """LLM-generate 1–2 clarifying questions based on missing_info + ticket text.

        On error or unexpected response shape falls back to converting each
        ``missing_info`` item into a plain question string.
        """
        text: str = state["text"]
        missing: list[str] = list(state.get("missing_info") or [])
        try:
            missing_str = "\n".join(f"- {item}" for item in missing)
            user = f"Ticket:\n{text}\n\nMissing information:\n{missing_str}"
            result = chat_model.complete_json(CLARIFY_SYSTEM, user)
            raw = result.get("clarification", [])
            if isinstance(raw, list):
                questions: list[str] = [str(q) for q in raw if q]
                if questions:
                    rationale = f"LLM generated {len(questions)} clarifying question(s)."
                    return {
                        "clarification": questions,
                        "reasoning": _with_reasoning(state, "clarify", rationale),
                    }
            # Response was valid JSON but missing the expected key/shape — use fallback.
            return {
                "clarification": [f"Could you provide: {item}?" for item in missing],
                "reasoning": _with_reasoning(
                    state, "clarify", "LLM response missing expected shape; used fallback Qs."
                ),
            }
        except Exception:
            _logger.exception("clarify node: LLM call failed; falling back to missing_info Qs")
            return {
                "clarification": [f"Could you provide: {item}?" for item in missing] or [],
                "reasoning": _with_reasoning(
                    state, "clarify", "LLM call failed; used fallback missing_info questions."
                ),
            }

    # ------------------------------------------------------------------
    # Wire edges:
    #   START → retrieve → classify → sentiment → assess_missing
    #         → score → decide ◇
    #                    ├ answer   → draft_reply → END
    #                    ├ clarify  → clarify     → END
    #                    └ escalate → END
    # ------------------------------------------------------------------

    builder: StateGraph[TicketState] = StateGraph(TicketState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("classify", classify)
    builder.add_node("sentiment", sentiment)
    builder.add_node("assess_missing", assess_missing)
    builder.add_node("score", score)
    builder.add_node("decide", decide)
    builder.add_node("draft_reply", draft_reply)
    builder.add_node("clarify", clarify)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "classify")
    builder.add_edge("classify", "sentiment")
    builder.add_edge("sentiment", "assess_missing")
    builder.add_edge("assess_missing", "score")
    builder.add_edge("score", "decide")
    builder.add_conditional_edges(
        "decide",
        router,
        {"answer": "draft_reply", "clarify": "clarify", "escalate": END},
    )
    builder.add_edge("draft_reply", END)
    builder.add_edge("clarify", END)

    return builder.compile()


def build_default_graph() -> Any:
    """Build the graph from live settings (real Voyage + BM25 + Pinecone + Groq).

    Deferred construction (not at import) so the app boots without keys/artifact present.
    """
    from app.analyze.baseline import _BM25_ARTIFACT
    from app.providers.chat import get_chat_model
    from app.providers.embeddings import get_embedder

    return build_graph(
        embedder=get_embedder(),
        sparse_encoder=BM25SparseEncoder.load(_BM25_ARTIFACT),
        store=PineconeStore(),
        chat_model=get_chat_model(),
    )
