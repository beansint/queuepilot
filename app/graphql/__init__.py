"""GraphQL transport (Slice F — D17).

Additive ``/graphql`` surface over the *same* services as the REST API — GraphQL is a second
adapter, not a second brain, so REST/GraphQL parity is structural. See
``docs/final-build-plan/13-SLICE-F-DESIGN.md`` and ``03-API-CONTRACT.md`` (GraphQL section).
"""

from __future__ import annotations

# NB: only re-export the router factory. Importing the `schema` *instance* here would rebind the
# package attribute ``app.graphql.schema`` from the submodule to the instance, breaking
# ``monkeypatch.setattr("app.graphql.schema....")`` in tests. Import the instance directly from
# ``app.graphql.schema`` where needed (e.g. the learn script).
from app.graphql.schema import build_graphql_router

__all__ = ["build_graphql_router"]
