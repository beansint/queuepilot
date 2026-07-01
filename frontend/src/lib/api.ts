import type { AnalyzeResponse } from "@/lib/types"

/**
 * Analyze a ticket via POST /analyze?explain=true (same-origin: the Vite dev
 * proxy forwards to FastAPI on :8000; in prod FastAPI serves the built app).
 *
 * Always requests `explain=true` so the console can render the confidence
 * breakdown, decision scale, and node trace from real `debug` data.
 */
export async function analyzeTicket(text: string): Promise<AnalyzeResponse> {
  const res = await fetch("/analyze?explain=true", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // ignore body parse failure — fall back to status text
    }
    throw new Error(detail)
  }

  return (await res.json()) as AnalyzeResponse
}
