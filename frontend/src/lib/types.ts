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

/** One calibration bucket row in a snapshot's reliability table (mirrors
 * `eval/card.py`'s `reliability` list — see `app/eval_api.py::ReliabilityBucket`). */
export interface ReliabilityBucket {
  lo: number
  hi: number
  n: number
  claimed: number | null
  accuracy: number | null
}

/** Aggregate metrics for one eval run (mirrors `app/eval_api.py::SnapshotMetrics`,
 * itself modeled on the real dict shape built by `eval/card.py::build_card`). All
 * fields are optional/nullable — a partial eval run renders as "n/a" rather than
 * being rounded up to a full score. */
export interface SnapshotMetrics {
  n: number | null
  config: Record<string, unknown> | null
  queue_match: number | null
  priority_match: number | null
  type_match: number | null
  label_recall_at_k: number | null
  reply_quality: number | null
  ece: number | null
  reliability: ReliabilityBucket[]
  skipped_evaluators: string[]
}

/** Full card payload for one snapshot — `GET /eval/snapshots/{name}`. */
export interface SnapshotCard {
  metrics: SnapshotMetrics
  baseline: SnapshotMetrics | null
}

/** One row in the `GET /eval/snapshots` listing. */
export interface SnapshotSummary {
  name: string
  n: number | null
  config: Record<string, unknown> | null
  queue_match: number | null
  priority_match: number | null
  type_match: number | null
  label_recall_at_k: number | null
  reply_quality: number | null
  ece: number | null
}

export interface SnapshotListResponse {
  snapshots: SnapshotSummary[]
}
