/** Types mirroring app/schemas.py (AnalyzeRequest/AnalyzeResponse/SimilarTicket) and the
 * `debug` / `trace` shapes built in app/analyze/graph_analyzer.py + app/analyze/trace.py.
 */

export interface SimilarTicket {
  score: number
  queue: string | null
  priority: string | null
  type: string | null
  snippet: string
}

export interface TraceSummary {
  enabled: boolean
  run_id?: string | null
  url?: string | null
  latency_ms?: number | null
  project?: string | null
}

export interface DebugNode {
  name: string
  rationale: string
}

export interface DebugRetrievalItem {
  score: number
  queue: string | null
  priority: string | null
  type: string | null
  snippet: string
}

export interface ConfidenceBreakdown {
  agreement: number
  top_score: number
  sigmoid_top_score: number
  consistency: number
  penalty: number
  final: number
  w_agreement: number
  w_score: number
  w_consistency: number
  penalty_missing: number
}

export interface SlaBreakdown {
  priority: string | null
  priority_weight: number
  frustration: number
  has_missing: boolean
  final: number
  w_priority: number
  w_frustration: number
  w_missing: number
}

export interface DebugPayload {
  nodes: DebugNode[]
  retrieval: DebugRetrievalItem[]
  confidence_breakdown: ConfidenceBreakdown
  sla_breakdown: SlaBreakdown
  decision: string
}

export interface Sentiment {
  frustration: number
  negativity: number
}

export interface FeedbackRequest {
  run_id: string
  score: 0 | 1
  correction?: { queue?: string; priority?: string; type?: string } | null
  comment?: string | null
  text?: string | null
}

export interface AuthStatus {
  required: boolean
  authenticated: boolean
}

export interface AnalyzeResponse {
  category: string | null
  queue: string | null
  priority: string | null
  confidence: number
  similar_tickets: SimilarTicket[]
  sentiment: Sentiment | null
  sla_risk: number | null
  escalate: boolean | null
  clarification: string[] | null
  suggested_reply: string | null
  trace: TraceSummary | null
  debug: DebugPayload | null
}
