"""Strawberry GraphQL types + mappers from the Pydantic ``AnalyzeResponse`` envelope (F3).

Hand-written types (not ``strawberry.experimental.pydantic``) so the loose ``dict`` fields on the
envelope map deliberately and stay clean under mypy --strict:

- ``sentiment`` ``{frustration, negativity}`` → a typed :class:`Sentiment` object.
- ``trace`` / ``debug`` (genuinely loose summaries) → the ``JSON`` scalar.
- everything else maps 1:1; Strawberry auto-camelCases field names (``sla_risk`` → ``slaRisk``).

The mappers (:meth:`Analysis.from_response`, etc.) are the single translation point between the REST
envelope and the GraphQL shape, guaranteeing parity: resolvers run the same service, then map here.
"""

from __future__ import annotations

from typing import cast

import strawberry
from strawberry.scalars import JSON

from app.schemas import AnalyzeResponse
from app.schemas import SimilarTicket as PydanticSimilarTicket


@strawberry.type
class Sentiment:
    """Typed view of the envelope's ``sentiment`` dict."""

    frustration: float
    negativity: float


@strawberry.type
class SimilarTicket:
    """One retrieved historical neighbor (mirrors the REST ``SimilarTicket``)."""

    score: float
    snippet: str
    queue: str | None = None
    priority: str | None = None
    # GraphQL field name stays ``type``; the Python attribute shadows the builtin only in this
    # class body, which is harmless (annotation-only field).
    type: str | None = None

    @classmethod
    def from_pydantic(cls, ticket: PydanticSimilarTicket) -> SimilarTicket:
        return cls(
            score=ticket.score,
            snippet=ticket.snippet,
            queue=ticket.queue,
            priority=ticket.priority,
            type=ticket.type,
        )


@strawberry.type
class Analysis:
    """GraphQL view of ``AnalyzeResponse`` (1:1, camelCased). Parity is enforced by the mapper."""

    confidence: float
    similar_tickets: list[SimilarTicket]
    category: str | None = None
    queue: str | None = None
    priority: str | None = None
    sentiment: Sentiment | None = None
    sla_risk: float | None = None
    escalate: bool | None = None
    clarification: list[str] | None = None
    suggested_reply: str | None = None
    trace: JSON | None = None
    debug: JSON | None = None

    @classmethod
    def from_response(cls, response: AnalyzeResponse) -> Analysis:
        """Map a REST ``AnalyzeResponse`` to the GraphQL ``Analysis`` type (the parity boundary)."""
        raw_sentiment = response.sentiment
        sentiment = (
            Sentiment(
                frustration=float(raw_sentiment.get("frustration", 0.0)),
                negativity=float(raw_sentiment.get("negativity", 0.0)),
            )
            if raw_sentiment is not None
            else None
        )
        return cls(
            confidence=response.confidence,
            similar_tickets=[SimilarTicket.from_pydantic(t) for t in response.similar_tickets],
            category=response.category,
            queue=response.queue,
            priority=response.priority,
            sentiment=sentiment,
            sla_risk=response.sla_risk,
            escalate=response.escalate,
            clarification=list(response.clarification) if response.clarification else None,
            suggested_reply=response.suggested_reply,
            # trace/debug are loose summary dicts exposed as the JSON scalar.
            trace=cast("JSON | None", response.trace),
            debug=cast("JSON | None", response.debug),
        )


@strawberry.type
class Health:
    """GraphQL mirror of ``GET /health``."""

    status: str
    app: str
    environment: str


@strawberry.input
class FeedbackInput:
    """Input for ``submitFeedback`` — mirrors the REST ``FeedbackRequest`` body."""

    run_id: str
    score: int
    correction: JSON | None = None
    comment: str | None = None
    text: str | None = None
