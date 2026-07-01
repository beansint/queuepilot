import { describe, expect, it } from "vitest"
import {
  CLARIFY_MAX,
  ESCALATE_MAX,
  clamp01,
  confidenceContribution,
  formatPct,
  resolveDecision,
  resolveMissingInfo,
  slaContribution,
  zoneForConfidence,
} from "@/lib/derive"
import type { AnalyzeResponse } from "@/lib/types"
import { SAMPLE_RESPONSE } from "@/test/fixtures"

describe("clamp01", () => {
  it("clamps out-of-range and NaN values", () => {
    expect(clamp01(1.5)).toBe(1)
    expect(clamp01(-0.2)).toBe(0)
    expect(clamp01(0.42)).toBe(0.42)
    expect(clamp01(Number.NaN)).toBe(0)
  })
})

describe("zoneForConfidence", () => {
  it("maps confidence to the correct decision zone", () => {
    expect(zoneForConfidence(ESCALATE_MAX - 0.01)).toBe("escalate")
    expect(zoneForConfidence(ESCALATE_MAX)).toBe("clarify")
    expect(zoneForConfidence(CLARIFY_MAX - 0.01)).toBe("clarify")
    expect(zoneForConfidence(CLARIFY_MAX)).toBe("handle")
    expect(zoneForConfidence(0.9)).toBe("handle")
  })
})

describe("resolveDecision", () => {
  it("returns handle when escalate is false and nothing is missing", () => {
    expect(resolveDecision(SAMPLE_RESPONSE)).toBe("handle")
  })

  it("returns escalate when escalate is true", () => {
    expect(resolveDecision({ ...SAMPLE_RESPONSE, escalate: true })).toBe("escalate")
  })

  it("prefers debug.decision when it names escalate/clarify", () => {
    const clarifyResp: AnalyzeResponse = {
      ...SAMPLE_RESPONSE,
      escalate: null,
      debug: { ...SAMPLE_RESPONSE.debug!, decision: "clarify" },
    }
    expect(resolveDecision(clarifyResp)).toBe("clarify")
  })

  it("treats escalate=false + clarification present as clarify", () => {
    expect(
      resolveDecision({ ...SAMPLE_RESPONSE, escalate: false, clarification: ["What VPN client?"] }),
    ).toBe("clarify")
  })
})

describe("confidenceContribution", () => {
  it("weights each factor and exposes raw magnitudes", () => {
    const c = confidenceContribution(SAMPLE_RESPONSE.debug!.confidence_breakdown)
    expect(c.agreement).toBeCloseTo(0.4, 5)
    expect(c.score).toBeCloseTo(0.19, 5)
    expect(c.consistency).toBeCloseTo(0.2, 5)
    expect(c.penalty).toBeCloseTo(0.15, 5)
    expect(c.rawAgreement).toBeCloseTo(0.8, 5)
  })
})

describe("slaContribution", () => {
  it("weights priority, frustration, and missing-info", () => {
    const s = slaContribution(SAMPLE_RESPONSE.debug!.sla_breakdown)
    expect(s.priority).toBeCloseTo(0.5, 5)
    expect(s.frustration).toBeCloseTo(0.28 * 0.72, 5)
    expect(s.missing).toBeCloseTo(0.15, 5)
    expect(s.rawMissing).toBe(1)
  })
})

describe("formatPct", () => {
  it("rounds to a whole-percent string", () => {
    expect(formatPct(0.64)).toBe("64%")
    expect(formatPct(0.999)).toBe("100%")
  })
})

describe("resolveMissingInfo", () => {
  it("uses clarification[] when present", () => {
    const resp = { ...SAMPLE_RESPONSE, clarification: ["Which VPN client?", "What version?"] }
    expect(resolveMissingInfo(resp)).toEqual(["Which VPN client?", "What version?"])
  })

  it("derives from the assess_missing node when clarification is null", () => {
    // SAMPLE_RESPONSE has clarification: null and an assess_missing rationale with a colon.
    expect(resolveMissingInfo(SAMPLE_RESPONSE)).toEqual(["VPN client + version"])
  })

  it("returns nothing-missing when the node reports no missing details", () => {
    const resp: AnalyzeResponse = {
      ...SAMPLE_RESPONSE,
      clarification: null,
      debug: {
        ...SAMPLE_RESPONSE.debug!,
        nodes: [
          { name: "assess_missing", rationale: "No missing details — enough context to answer" },
        ],
      },
    }
    expect(resolveMissingInfo(resp)).toEqual([])
  })

  it("falls back gracefully when debug is absent", () => {
    expect(resolveMissingInfo({ ...SAMPLE_RESPONSE, clarification: null, debug: null })).toEqual([])
  })
})
