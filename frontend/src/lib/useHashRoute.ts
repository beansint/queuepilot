import { useCallback, useEffect, useState } from "react"

/**
 * The console's client-side routes. Kept intentionally tiny — this is a
 * dependency-free hash router (no react-router) for the handful of real
 * destinations the console has:
 *   - "console"  → the ticket-analysis workspace (default / empty hash)
 *   - "evidence" → the full similar-tickets evidence page (needs a result)
 *   - "overview" → the marketing landing page, viewable while logged in
 */
export type Route = "console" | "evidence" | "overview"

const HASH_TO_ROUTE: Record<string, Route> = {
  "": "console",
  "#": "console",
  "#/": "console",
  "#/evidence": "evidence",
  "#/overview": "overview",
}

const ROUTE_TO_HASH: Record<Route, string> = {
  console: "#/",
  evidence: "#/evidence",
  overview: "#/overview",
}

/** Parse `window.location.hash` into a known route, defaulting to the console. */
export function routeFromHash(hash: string): Route {
  return HASH_TO_ROUTE[hash] ?? "console"
}

/**
 * Subscribe to the URL hash and expose `{ route, navigate }`. `navigate` sets
 * the hash (which fires `hashchange`, updating `route`), so the browser Back
 * button and shareable URLs both work with no extra bookkeeping.
 */
export function useHashRoute(): { route: Route; navigate: (route: Route) => void } {
  const [route, setRoute] = useState<Route>(() =>
    typeof window === "undefined" ? "console" : routeFromHash(window.location.hash),
  )

  useEffect(() => {
    function onHashChange() {
      setRoute(routeFromHash(window.location.hash))
    }
    window.addEventListener("hashchange", onHashChange)
    return () => window.removeEventListener("hashchange", onHashChange)
  }, [])

  const navigate = useCallback((next: Route) => {
    // Update the URL for shareability + Back-button history, and set state directly
    // rather than waiting on the `hashchange` event (which some environments don't
    // fire when the hash is set programmatically). The listener still covers real
    // back/forward navigation; a redundant same-value setRoute there is a no-op.
    window.location.hash = ROUTE_TO_HASH[next]
    setRoute(next)
  }, [])

  return { route, navigate }
}
