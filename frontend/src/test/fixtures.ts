import type { AnalyzeResponse } from "@/lib/types"

/**
 * A representative /analyze?explain=true response (VPN ticket) reused across tests.
 * Mirrors the shape produced by app/analyze/graph_analyzer.py (_build_debug + trace).
 */
export const SAMPLE_RESPONSE: AnalyzeResponse = {
  category: "Incident",
  queue: "Technical Support",
  priority: "High",
  confidence: 0.64,
  similar_tickets: [
    {
      score: 0.42,
      queue: "Technical Support",
      priority: "High",
      type: "Incident",
      snippet: "VPN fails to connect after Windows 11 22H2 update",
    },
    {
      score: 0.39,
      queue: "Technical Support",
      priority: "High",
      type: "Incident",
      snippet: "Cannot reach corporate VPN after patch Tuesday",
    },
    {
      score: 0.31,
      queue: "IT",
      priority: "Medium",
      type: "Problem",
      snippet: "GlobalProtect drops connection post Windows update",
    },
  ],
  sentiment: { frustration: 0.72, negativity: 0.4 },
  sla_risk: 0.85,
  escalate: false,
  clarification: null,
  suggested_reply:
    "Hi — sorry you're dealing with this right before a demo. Could you tell me which VPN client and version you're on?",
  trace: {
    enabled: true,
    run_id: "a1f4c7e2",
    url: "https://smith.langchain.com/o/x/r/a1f4c7e2",
    latency_ms: 1240,
    project: "queuepilot",
  },
  debug: {
    nodes: [
      { name: "retrieve", rationale: "5 similar tickets via hybrid search" },
      { name: "classify", rationale: "Incident / Technical Support / High from 5 neighbors" },
      { name: "sentiment", rationale: "frustration 0.72, negativity 0.40" },
      { name: "assess_missing", rationale: "1 missing detail: VPN client + version" },
      { name: "score", rationale: "confidence 0.64, sla_risk 0.85" },
      { name: "decide", rationale: "answer (confidence >= 0.62 -> handle now, not escalate)" },
    ],
    retrieval: [
      {
        score: 0.42,
        queue: "Technical Support",
        priority: "High",
        type: "Incident",
        snippet: "VPN fails to connect after Windows 11 22H2 update",
      },
    ],
    confidence_breakdown: {
      agreement: 0.8,
      top_score: 0.42,
      sigmoid_top_score: 0.38,
      consistency: 0.5,
      penalty: 0.15,
      final: 0.64,
      w_agreement: 0.5,
      w_score: 0.5,
      w_consistency: 0.4,
      penalty_missing: 0.15,
    },
    sla_breakdown: {
      priority: "high",
      priority_weight: 1.0,
      frustration: 0.72,
      has_missing: true,
      final: 0.85,
      w_priority: 0.5,
      w_frustration: 0.28,
      w_missing: 0.15,
    },
    decision: "answer",
  },
}
