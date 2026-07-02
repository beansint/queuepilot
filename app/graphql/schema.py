"""GraphQL schema + resolvers (F4) and the gated router factory (F5).

Resolvers call the **same** service entry points as the REST API
(``get_graph_analyzer().analyze()``, ``submit_feedback()``) and reuse the same request-validation
(``AnalyzeRequest``) — so GraphQL results are at parity with REST and there is no duplicated logic.

Gating (F5): the router reuses the REST dependencies ``require_auth`` + ``rate_limit`` verbatim, so
``/graphql`` is invite-gated + rate-limited exactly like ``POST /analyze`` (one source of truth).
GraphiQL therefore requires login first — consistent with the invite-gated demo.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

import strawberry
from fastapi import Depends
from langsmith import Client
from strawberry.fastapi import GraphQLRouter

from app.analyze.graph_analyzer import get_graph_analyzer
from app.auth import require_auth
from app.config import get_settings
from app.feedback import get_feedback_client, submit_feedback
from app.graphql.types import Analysis, FeedbackInput, Health
from app.ratelimit import rate_limit
from app.schemas import AnalyzeRequest, FeedbackRequest


@lru_cache(maxsize=1)
def _cached_feedback_client() -> Client | None:
    """Build + cache the LangSmith client for ``submitFeedback`` (mirrors ``app.main``).

    Local to this module (not imported from ``app.main``) to avoid a circular import — ``app.main``
    imports this module to mount the router. Returns ``None`` (also cached) when LangSmith is
    unconfigured, so unconfigured deployments no-op cheaply.
    """
    return get_feedback_client()


@strawberry.type
class Query:
    @strawberry.field
    def analyze(self, text: str, explain: bool = False) -> Analysis:
        """Analyze a support ticket (parity with REST ``POST /analyze``)."""
        # Reuse the REST request validator (non-empty, <= MAX_INPUT_CHARS) so an empty/oversized
        # ticket raises here and surfaces as a GraphQL error — parity with REST's 422.
        req = AnalyzeRequest(text=text)
        response = get_graph_analyzer().analyze(req.text, explain=explain)
        return Analysis.from_response(response)

    @strawberry.field
    def health(self) -> Health:
        """Liveness/info (mirrors REST ``GET /health``)."""
        settings = get_settings()
        return Health(status="ok", app=settings.app_name, environment=settings.environment)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def submit_feedback(self, input: FeedbackInput) -> bool:
        """Submit human feedback on a prior analyze run (parity with REST ``POST /feedback``)."""
        # Reuse the REST request model (validates run_id non-empty, score in {0,1}).
        req = FeedbackRequest(
            run_id=input.run_id,
            score=input.score,
            correction=cast("dict[str, Any] | None", input.correction),
            comment=input.comment,
            text=input.text,
        )
        result = submit_feedback(req, client=_cached_feedback_client())
        return bool(result.get("ok", False))


schema = strawberry.Schema(query=Query, mutation=Mutation)


def build_graphql_router() -> GraphQLRouter[None, None]:
    """Build the gated GraphQL router (GraphiQL enabled).

    Reuses the REST auth + rate-limit dependencies so ``/graphql`` is protected identically to
    ``POST /analyze``: ``401`` without a valid ``qp_session`` cookie when auth is configured (open
    when unconfigured — graceful degradation), and ``429`` past the per-IP limit / daily cap.
    """
    return GraphQLRouter(
        schema,
        dependencies=[Depends(require_auth), Depends(rate_limit)],
    )
