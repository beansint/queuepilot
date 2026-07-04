import type { AnalyzeResponse, AuthStatus, FeedbackRequest } from "@/lib/types"

/** Shared 401-aware error, so callers can special-case "please log in" vs other failures. */
export class AuthRequiredError extends Error {
  constructor(message = "Invite code required") {
    super(message)
    this.name = "AuthRequiredError"
  }
}

async function _extractDetail(res: Response): Promise<string> {
  let detail = `Request failed with status ${res.status}`
  try {
    const body = await res.json()
    if (body?.detail) {
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    }
  } catch {
    // ignore body parse failure — fall back to status text
  }
  return detail
}

/**
 * Analyze a ticket via POST /analyze?explain=true (same-origin: the Vite dev
 * proxy forwards to FastAPI on :8000; in prod FastAPI serves the built app).
 *
 * Always requests `explain=true` so the console can render the confidence
 * breakdown, decision scale, and node trace from real `debug` data.
 *
 * Throws `AuthRequiredError` on 401 (invite-code session missing/expired) so
 * callers can route back to the login gate instead of showing a generic error.
 */
export async function analyzeTicket(text: string): Promise<AnalyzeResponse> {
  const res = await fetch("/analyze?explain=true", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })

  if (res.status === 401) {
    throw new AuthRequiredError(await _extractDetail(res))
  }
  if (!res.ok) {
    throw new Error(await _extractDetail(res))
  }

  return (await res.json()) as AnalyzeResponse
}

/**
 * Post human feedback (thumbs + optional correction) for a prior /analyze run,
 * joined by `run_id` (Slice C's `trace.run_id`). Same-origin, same error-handling
 * style as `analyzeTicket` (including the 401 -> AuthRequiredError mapping).
 */
export async function postFeedback(req: FeedbackRequest): Promise<void> {
  const res = await fetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })

  if (res.status === 401) {
    throw new AuthRequiredError(await _extractDetail(res))
  }
  if (!res.ok) {
    throw new Error(await _extractDetail(res))
  }
}

/**
 * Whether invite-code auth is required for this deployment, and whether the
 * current browser session is already authenticated. Always open (never 401s)
 * so the app can decide whether to render the login gate.
 */
export async function getAuthStatus(): Promise<AuthStatus> {
  const res = await fetch("/auth/status")
  if (!res.ok) {
    throw new Error(await _extractDetail(res))
  }
  return (await res.json()) as AuthStatus
}

/**
 * Exchange an invite code for a signed session cookie via POST /login.
 * Throws on a wrong code (401) or any other failure; resolves on success.
 */
export async function login(code: string): Promise<void> {
  const res = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  })

  if (res.status === 401) {
    throw new AuthRequiredError(await _extractDetail(res))
  }
  if (!res.ok) {
    throw new Error(await _extractDetail(res))
  }
}

/**
 * Clear the session cookie via POST /logout (endpoint at app/main.py). Always
 * resolves on a 2xx; throws on any non-ok response so the caller can surface a
 * "couldn't sign out" toast and stay put rather than half-clearing UI state.
 */
export async function logout(): Promise<void> {
  const res = await fetch("/logout", { method: "POST" })
  if (!res.ok) {
    throw new Error(await _extractDetail(res))
  }
}
