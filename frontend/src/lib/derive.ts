import type { AnalyzeResponse, ConfidenceBreakdown, SlaBreakdown } from "@/lib/types"

/** Decision-scale zone boundaries (matches the locked mockup's decision scale). */
export const ESCALATE_MAX = 0.35
export const CLARIFY_MAX = 0.62

export type Decision = "escalate" | "clarify" | "handle"

export function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(1, value))
}

/** Which zone the confidence score falls in on the decision scale. */
export function zoneForConfidence(confidence: number): Decision {
  if (confidence < ESCALATE_MAX) return "escalate"
  if (confidence < CLARIFY_MAX) return "clarify"
  return "handle"
}

/**
 * The console's headline decision. Prefers explicit signals from the API
 * (`escalate`, `debug.decision`) over the raw confidence zone, since the
 * backend's actual routing logic is the source of truth.
 */
export function resolveDecision(response: AnalyzeResponse): Decision {
  if (response.escalate === true) return "escalate"
  const raw = response.debug?.decision?.toLowerCase()
  if (raw?.includes("escalate")) return "escalate"
  if (raw?.includes("clarify")) return "clarify"
  if (response.escalate === false) {
    if (response.clarification && response.clarification.length > 0) return "clarify"
    return "handle"
  }
  return zoneForConfidence(response.confidence)
}

export function decisionCopy(decision: Decision): { label: string; sub: string } {
  switch (decision) {
    case "escalate":
      return { label: "Escalate", sub: "Confidence too low to handle automatically" }
    case "clarify":
      return { label: "Needs clarification", sub: "Ask the customer before proceeding" }
    default:
      return { label: "Handle now", sub: "Confident enough to handle now" }
  }
}

export function handleLineSubline(confidence: number, decision: Decision): string {
  const diff = Math.abs(confidence - CLARIFY_MAX)
  const formatted = diff.toFixed(2)
  if (decision === "handle") return `+${formatted} over the handle line`
  if (decision === "clarify") return `${formatted} below the handle line`
  return `${Math.abs(confidence - ESCALATE_MAX).toFixed(2)} from the escalate line`
}

export interface ConfidenceContribution {
  agreement: number
  score: number
  consistency: number
  penalty: number
  rawAgreement: number
  rawScore: number
  rawConsistency: number
  rawPenalty: number
}

/** Weighted contribution + raw magnitude for each confidence-breakdown factor. */
export function confidenceContribution(b: ConfidenceBreakdown): ConfidenceContribution {
  return {
    agreement: b.w_agreement * b.agreement,
    score: b.w_score * b.sigmoid_top_score,
    consistency: b.w_consistency * b.consistency,
    penalty: b.penalty,
    rawAgreement: clamp01(b.agreement),
    rawScore: clamp01(b.sigmoid_top_score),
    rawConsistency: clamp01(b.consistency),
    rawPenalty: clamp01(b.penalty),
  }
}

export interface SlaContribution {
  priority: number
  frustration: number
  missing: number
  rawPriority: number
  rawFrustration: number
  rawMissing: number
}

export function slaContribution(b: SlaBreakdown): SlaContribution {
  return {
    priority: b.w_priority * b.priority_weight,
    frustration: b.w_frustration * b.frustration,
    missing: b.w_missing * (b.has_missing ? 1 : 0),
    rawPriority: clamp01(b.priority_weight),
    rawFrustration: clamp01(b.frustration),
    rawMissing: b.has_missing ? 1 : 0,
  }
}

/**
 * Missing-info items for the summary rail.
 *
 * Prefers the explicit `clarification[]` list (populated on the clarify path).
 * When that's absent but `debug` is present, derives the finding from the
 * `assess_missing` node's rationale — the node runs on every request, so its
 * rationale reflects whether details are missing even when the workflow didn't
 * route to clarify. Returns `[]` (graceful "nothing missing") when neither
 * source indicates a gap or when `debug` is absent.
 */
export function resolveMissingInfo(response: AnalyzeResponse): string[] {
  if (response.clarification && response.clarification.length > 0) {
    return response.clarification
  }

  const rationale = response.debug?.nodes.find((n) => n.name === "assess_missing")?.rationale?.trim()
  if (!rationale) return []

  const lower = rationale.toLowerCase()
  // Node reported nothing missing.
  if (
    /\bno\s+missing\b/.test(lower) ||
    /\bnothing\s+missing\b/.test(lower) ||
    /\bnone\b/.test(lower) ||
    /^0\b/.test(lower) ||
    /\b0\s+missing\b/.test(lower)
  ) {
    return []
  }

  // Prefer the descriptive tail after a colon (e.g. "1 missing detail: VPN client + version").
  const colonIdx = rationale.indexOf(":")
  if (colonIdx !== -1 && colonIdx < rationale.length - 1) {
    return [rationale.slice(colonIdx + 1).trim()]
  }
  return [rationale]
}

export function sentimentLabel(value: number): string {
  if (value >= 0.66) return "High"
  if (value >= 0.33) return "Moderate"
  return "Low"
}

export function riskLabel(value: number): string {
  if (value >= 0.66) return "High"
  if (value >= 0.33) return "Moderate"
  return "Low"
}

export function formatPct(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}
