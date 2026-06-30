"""B8/B9 — offline tests for score, decide, draft_reply, and clarify LangGraph nodes.

All tests use fake dependencies (no network, no Groq, no Pinecone). Three routing branches
are verified end-to-end: answer, clarify, and escalate.

FakeChat variants encode specific scoring scenarios by returning different classify/sentiment/
assess_missing values. FakeStore variants let us control neighbor agreement and top score.
"""

from __future__ import annotations

from typing import Any

from app.analyze.graph import (
    ESCALATE_CONFIDENCE_BELOW,
    ESCALATE_SLA_RISK_ABOVE,
    build_graph,
    route_decision,
)
from app.providers.embeddings import EMBED_DIM
from app.retrieval.pinecone_store import Neighbor
from app.retrieval.sparse import SparseVector

# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBED_DIM


class _FakeEncoder:
    def encode_query(self, text: str) -> SparseVector:
        return {"indices": [1, 2], "values": [0.5, 0.5]}


#: High-agreement neighbors — both have the same queue and a strong retrieval score.
_AGREE_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.9, queue="IT Support", priority="low", type="Incident", snippet="VPN fix"),
    Neighbor(score=0.7, queue="IT Support", priority="low", type="Incident", snippet="Network"),
]

#: Low-agreement neighbors — each has a different queue and a weak retrieval score.
_DIVERSE_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.2, queue="IT Support",  priority="low", type="Incident",  snippet="a"),
    Neighbor(score=0.15, queue="Billing",    priority="low", type="Request",   snippet="b"),
    Neighbor(score=0.1, queue="Facilities",  priority="low", type="Request",   snippet="c"),
]


class _FakeStoreAgree:
    """Returns the high-agreement neighbor set."""

    def hybrid_query(
        self, dense: list[float], sparse: SparseVector, top_k: int = 5
    ) -> list[Neighbor]:
        return _AGREE_NEIGHBORS[:top_k]


class _FakeStoreDiverse:
    """Returns the low-agreement/low-score neighbor set."""

    def hybrid_query(
        self, dense: list[float], sparse: SparseVector, top_k: int = 5
    ) -> list[Neighbor]:
        return _DIVERSE_NEIGHBORS[:top_k]


# ---------------------------------------------------------------------------
# FakeChat variants — each encodes a specific scoring scenario
# ---------------------------------------------------------------------------


class _FakeChatAnswer:
    """Returns classify/sentiment/assess_missing values that produce an 'answer' route.

    Designed so that:
    - llm_queue matches majority_queue ("IT Support") → consistency bonus applied.
    - missing_info is empty → no penalty, no clarify branch.
    - frustration=0.1, priority="low" → sla_risk well below 0.7.
    - With top_score=0.9, agreement=1.0: confidence ≈ 0.913 > 0.4.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return "Your VPN issue should be resolved by restarting the VPN client and flushing DNS."

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "IT Support",  # matches majority → consistency bonus
            "priority": "low",
            "frustration": 0.1,
            "negativity": 0.1,
            "missing_info": [],
        }


class _FakeChatClarify:
    """Returns values that produce a 'clarify' route.

    Designed so that:
    - missing_info is non-empty → penalty applied but confidence still > 0.4.
    - priority="low", frustration=0.1 → sla_risk well below 0.7.
    - complete_json also provides the "clarification" key for the clarify node.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "Billing",  # differs from neighbor majority → mid confidence (clarify band)
            "priority": "low",
            "frustration": 0.1,
            "negativity": 0.1,
            "missing_info": ["no error code"],
            "clarification": ["What error code do you see?"],
        }


class _FakeChatEscalateHighSla:
    """Returns values that produce an 'escalate' route via extreme SLA risk + non-high confidence.

    high priority + high frustration + missing → sla_risk = 0.5 + 0.27 + 0.2 = 0.97 > 0.85.
    queue mismatch + missing penalty → confidence ≈ 0.56 (< 0.70) → SLA escalation fires.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "Billing",  # differs from majority → confidence below the answer band
            "priority": "high",
            "frustration": 0.9,
            "negativity": 0.8,
            "missing_info": ["no logs attached"],
        }


class _FakeChatEscalateLowConf:
    """Returns values that produce an 'escalate' route via low confidence.

    LLM queue="Billing" differs from majority_queue="IT Support" → no consistency bonus.
    With top_score=0.2, agreement≈0.333: confidence ≈ 0.324 < 0.4.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Request",
            "queue": "Billing",   # deliberately different from majority "IT Support"
            "priority": "low",
            "frustration": 0.2,
            "negativity": 0.1,
            "missing_info": [],
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build_agree(chat: Any) -> Any:
    """Graph backed by high-agreement neighbors."""
    return build_graph(
        _FakeEmbedder(),
        _FakeEncoder(),  # type: ignore[arg-type]
        _FakeStoreAgree(),  # type: ignore[arg-type]
        chat,
        top_k=2,
        alpha=0.5,
    )


def _build_diverse(chat: Any) -> Any:
    """Graph backed by low-agreement/diverse-queue neighbors."""
    return build_graph(
        _FakeEmbedder(),
        _FakeEncoder(),  # type: ignore[arg-type]
        _FakeStoreDiverse(),  # type: ignore[arg-type]
        chat,
        top_k=3,
        alpha=0.5,
    )


# ---------------------------------------------------------------------------
# route_decision unit tests (pure function, no graph)
# ---------------------------------------------------------------------------


def test_route_decision_answer() -> None:
    """High confidence + low sla_risk + no missing info → answer."""
    assert route_decision(0.85, 0.4, []) == "answer"


def test_route_decision_clarify() -> None:
    """Mid confidence (below the answer band) + low sla_risk + missing info → clarify."""
    assert route_decision(0.55, 0.3, ["no error code"]) == "clarify"


def test_route_decision_escalate_low_confidence() -> None:
    """confidence below threshold → escalate (even if no missing info)."""
    assert route_decision(ESCALATE_CONFIDENCE_BELOW - 0.01, 0.3, []) == "escalate"


def test_route_decision_escalate_high_sla_risk() -> None:
    """Extreme sla_risk + non-high confidence → escalate (high confidence would answer instead)."""
    assert route_decision(0.55, ESCALATE_SLA_RISK_ABOVE + 0.01, []) == "escalate"


def test_route_decision_escalate_takes_priority_over_clarify() -> None:
    """When BOTH low confidence and missing info, escalate wins over clarify."""
    assert route_decision(0.1, 0.2, ["no error code"]) == "escalate"


def test_route_decision_boundary_confidence() -> None:
    """At exactly ESCALATE_CONFIDENCE_BELOW (< is strict) → answer/clarify branch runs."""
    # Exactly at threshold is not < threshold, so no escalate from confidence alone.
    assert route_decision(ESCALATE_CONFIDENCE_BELOW, 0.3, []) == "answer"


def test_route_decision_boundary_sla_risk() -> None:
    """At exactly ESCALATE_SLA_RISK_ABOVE (> is strict) → no escalate from sla_risk alone."""
    assert route_decision(0.8, ESCALATE_SLA_RISK_ABOVE, []) == "answer"


# ---------------------------------------------------------------------------
# Full-graph: 'answer' branch
# ---------------------------------------------------------------------------


def test_answer_branch_decision_is_answer() -> None:
    """High confidence + no missing info → decision='answer', escalate=False."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "cannot connect to VPN"})
    assert result["decision"] == "answer"
    assert result["escalate"] is False


def test_answer_branch_suggested_reply_is_set() -> None:
    """The draft_reply node must populate suggested_reply with a non-empty string."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "cannot connect to VPN"})
    assert result.get("suggested_reply") is not None
    assert isinstance(result["suggested_reply"], str)
    assert len(result["suggested_reply"]) > 0


def test_answer_branch_no_clarification() -> None:
    """The clarification field must be absent (or not set) on the answer branch."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "cannot connect to VPN"})
    # clarification is not set on the answer path (LangGraph leaves it absent)
    assert "clarification" not in result or result.get("clarification") is None


def test_answer_branch_confidence_in_range() -> None:
    """Confidence from score node must be in [0.0, 1.0]."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "cannot connect to VPN"})
    assert 0.0 <= result["confidence"] <= 1.0


def test_answer_branch_sla_risk_in_range() -> None:
    """sla_risk from score node must be in [0.0, 1.0]."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "cannot connect to VPN"})
    assert 0.0 <= result["sla_risk"] <= 1.0


# ---------------------------------------------------------------------------
# Full-graph: 'clarify' branch
# ---------------------------------------------------------------------------


def test_clarify_branch_decision_is_clarify() -> None:
    """Non-empty missing info + safe confidence/sla_risk → decision='clarify'."""
    result = _build_agree(_FakeChatClarify()).invoke({"text": "something is broken"})
    assert result["decision"] == "clarify"
    assert result["escalate"] is False


def test_clarify_branch_clarification_is_set() -> None:
    """The clarify node must populate clarification with a non-empty list."""
    result = _build_agree(_FakeChatClarify()).invoke({"text": "something is broken"})
    clarification = result.get("clarification")
    assert isinstance(clarification, list)
    assert len(clarification) > 0


def test_clarify_branch_clarification_contains_strings() -> None:
    """All clarification items must be strings."""
    result = _build_agree(_FakeChatClarify()).invoke({"text": "something is broken"})
    for item in result["clarification"]:
        assert isinstance(item, str)


def test_clarify_branch_no_suggested_reply() -> None:
    """draft_reply does not run on the clarify branch — suggested_reply must be absent/None."""
    result = _build_agree(_FakeChatClarify()).invoke({"text": "something is broken"})
    assert "suggested_reply" not in result or result.get("suggested_reply") is None


# ---------------------------------------------------------------------------
# Full-graph: 'escalate' branch — via high SLA risk
# ---------------------------------------------------------------------------


def test_escalate_high_sla_risk_decision() -> None:
    """High priority + high frustration → sla_risk > 0.7 → escalate."""
    result = _build_agree(_FakeChatEscalateHighSla()).invoke({"text": "system is down NOW"})
    assert result["decision"] == "escalate"
    assert result["escalate"] is True
    assert result["sla_risk"] > ESCALATE_SLA_RISK_ABOVE


def test_escalate_high_sla_risk_no_reply() -> None:
    """draft_reply must not run on the escalate branch."""
    result = _build_agree(_FakeChatEscalateHighSla()).invoke({"text": "system is down NOW"})
    assert "suggested_reply" not in result or result.get("suggested_reply") is None


def test_escalate_high_sla_risk_no_clarification() -> None:
    """clarify must not run on the escalate branch."""
    result = _build_agree(_FakeChatEscalateHighSla()).invoke({"text": "system is down NOW"})
    assert "clarification" not in result or result.get("clarification") is None


# ---------------------------------------------------------------------------
# Full-graph: 'escalate' branch — via low confidence
# ---------------------------------------------------------------------------


def test_escalate_low_confidence_decision() -> None:
    """Diverse neighbors + LLM/majority mismatch → confidence < 0.4 → escalate."""
    result = _build_diverse(_FakeChatEscalateLowConf()).invoke({"text": "vague issue"})
    assert result["decision"] == "escalate"
    assert result["escalate"] is True
    assert result["confidence"] < ESCALATE_CONFIDENCE_BELOW


def test_escalate_low_confidence_no_reply() -> None:
    """draft_reply must not run when confidence triggers escalation."""
    result = _build_diverse(_FakeChatEscalateLowConf()).invoke({"text": "vague issue"})
    assert "suggested_reply" not in result or result.get("suggested_reply") is None


# ---------------------------------------------------------------------------
# Score node — spot checks via the full graph
# ---------------------------------------------------------------------------


def test_score_node_populates_confidence_and_sla_risk() -> None:
    """score node must always set both confidence and sla_risk."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "test ticket"})
    assert "confidence" in result
    assert "sla_risk" in result
    assert isinstance(result["confidence"], float)
    assert isinstance(result["sla_risk"], float)


def test_score_node_confidence_above_threshold_for_good_neighbors() -> None:
    """High-agreement neighbors + matching LLM queue → confidence well above 0.4."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "test ticket"})
    assert result["confidence"] >= ESCALATE_CONFIDENCE_BELOW


def test_score_node_confidence_below_threshold_for_diverse_neighbors() -> None:
    """Diverse neighbors + LLM/majority mismatch → confidence below 0.4."""
    result = _build_diverse(_FakeChatEscalateLowConf()).invoke({"text": "test ticket"})
    assert result["confidence"] < ESCALATE_CONFIDENCE_BELOW


# ---------------------------------------------------------------------------
# draft_reply error fallback
# ---------------------------------------------------------------------------


class _FakeChatAnswerWithBrokenComplete:
    """complete() raises — verifies draft_reply returns suggested_reply=None on error."""

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        raise RuntimeError("simulated complete() failure")

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "IT Support",
            "priority": "low",
            "frustration": 0.1,
            "negativity": 0.1,
            "missing_info": [],
        }


def test_draft_reply_fallback_on_error() -> None:
    """When complete() raises, draft_reply must return suggested_reply=None (no crash)."""
    result = _build_agree(_FakeChatAnswerWithBrokenComplete()).invoke({"text": "vpn issue"})
    assert result["decision"] == "answer"
    assert result.get("suggested_reply") is None


# ---------------------------------------------------------------------------
# clarify node — fallback when LLM returns unexpected shape
# ---------------------------------------------------------------------------


class _FakeChatClarifyNoKey:
    """complete_json succeeds but doesn't include 'clarification' in response.

    The clarify node must fall back to converting missing_info items to questions.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        # includes missing_info but NOT clarification → fallback should fire
        return {
            "category": "Incident",
            "queue": "Billing",  # differs from majority → clarify band
            "priority": "low",
            "frustration": 0.1,
            "negativity": 0.1,
            "missing_info": ["no error code", "no account id"],
        }


def test_clarify_fallback_when_no_clarification_key() -> None:
    """When LLM omits the 'clarification' key the node falls back to missing_info questions."""
    result = _build_agree(_FakeChatClarifyNoKey()).invoke({"text": "broken login"})
    assert result["decision"] == "clarify"
    clarification = result.get("clarification", [])
    assert isinstance(clarification, list)
    assert len(clarification) > 0
    # Fallback turns each missing_info item into a question
    for item in clarification:
        assert isinstance(item, str)
        assert len(item) > 0


class _FakeChatClarifyError:
    """complete_json raises on the clarify call (but classify/sentiment/assess succeed)."""

    _call_count: int = 0

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        # First 3 calls: classify, sentiment, assess_missing (succeed).
        # 4th call: clarify (raises).
        self._call_count += 1
        if self._call_count < 4:
            return {
                "category": "Incident",
                "queue": "Billing",  # differs from majority → clarify band
                "priority": "low",
                "frustration": 0.1,
                "negativity": 0.1,
                "missing_info": ["no error code"],
            }
        raise RuntimeError("simulated clarify LLM failure")


def test_clarify_fallback_on_exception() -> None:
    """When complete_json raises inside the clarify node the graph must not crash."""
    result = _build_agree(_FakeChatClarifyError()).invoke({"text": "broken login"})
    assert result["decision"] == "clarify"
    clarification = result.get("clarification", [])
    assert isinstance(clarification, list)


# ---------------------------------------------------------------------------
# Existing-graph compatibility — score + decide fields added without breakage
# ---------------------------------------------------------------------------


def test_existing_fields_still_populated() -> None:
    """All pre-B7 fields (category, queue, priority, sentiment, missing_info) remain set."""
    result = _build_agree(_FakeChatAnswer()).invoke(
        {"text": "My laptop won't boot after the latest update. Please help ASAP."}
    )
    assert result["category"] == "Incident"
    assert result["queue"] == "IT Support"
    assert result["priority"] == "low"
    assert result["sentiment"] is not None
    assert isinstance(result["missing_info"], list)
    assert result["text"].startswith("My laptop")


def test_new_fields_always_present() -> None:
    """score + decide must always set confidence, sla_risk, decision, and escalate."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "test"})
    assert "confidence" in result
    assert "sla_risk" in result
    assert "decision" in result
    assert "escalate" in result
    assert result["decision"] in {"answer", "clarify", "escalate"}
    assert isinstance(result["escalate"], bool)


def test_escalate_fields_not_filled_on_answer_branch() -> None:
    """On the 'answer' branch escalate must be False and clarification must be absent."""
    result = _build_agree(_FakeChatAnswer()).invoke({"text": "VPN down"})
    assert result["escalate"] is False
    assert "clarification" not in result or result.get("clarification") is None
