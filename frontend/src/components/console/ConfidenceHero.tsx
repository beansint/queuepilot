import { useState } from "react"
import { ChevronDown, Lightbulb, MapPin } from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { AnalyzeResponse, ConfidenceBreakdown } from "@/lib/types"
import {
  CLARIFY_MAX,
  ESCALATE_MAX,
  clamp01,
  confidenceContribution,
  decisionCopy,
  handleLineSubline,
  resolveDecision,
} from "@/lib/derive"
import { cn } from "@/lib/utils"

interface ConfidenceHeroProps {
  response: AnalyzeResponse
}

const FALLBACK_BREAKDOWN: ConfidenceBreakdown = {
  agreement: 0,
  top_score: 0,
  sigmoid_top_score: 0,
  consistency: 0,
  penalty: 0,
  final: 0,
  w_agreement: 0,
  w_score: 0,
  w_consistency: 0,
  penalty_missing: 0,
}

export function ConfidenceHero({ response }: ConfidenceHeroProps) {
  const [open, setOpen] = useState(false)
  const confidence = clamp01(response.confidence)
  const decision = resolveDecision(response)
  const copy = decisionCopy(decision)
  const breakdown = response.debug?.confidence_breakdown ?? FALLBACK_BREAKDOWN
  const contribution = confidenceContribution(breakdown)
  const total = breakdown.final || confidence
  const hasConsistency = contribution.consistency > 0.001

  const pillClasses =
    decision === "handle"
      ? "bg-positive/20 border-positive/40 text-[#86EFAC]"
      : decision === "clarify"
        ? "bg-warning/25 border-warning/50 text-[#FDE68A]"
        : "bg-destructive/25 border-destructive/50 text-[#FCA5A5]"
  const dotClasses =
    decision === "handle" ? "bg-[#4ADE80]" : decision === "clarify" ? "bg-[#FBBF24]" : "bg-[#F87171]"

  const actionText =
    decision === "escalate"
      ? "Confidence is too low to auto-handle — route this to a human before replying."
      : decision === "clarify" && response.clarification?.length
        ? `Reply needs more detail — ask for ${response.clarification[0].toLowerCase()} before closing.`
        : "Reply is grounded — send it, or make a light edit before closing."

  return (
    <section
      aria-label="Confidence score and decision breakdown"
      className="relative mb-5 overflow-hidden rounded-2xl border border-[#0A3A57] bg-hero p-4 text-white shadow-lg"
    >
      <div className="grid items-stretch gap-5.5 md:grid-cols-[34%_1fr]">
        {/* LEFT column */}
        <div className="flex flex-col gap-1.5 border-white/15 pr-5 md:border-r">
          <span className="font-mono text-[9.5px] font-bold tracking-[0.09em] text-white/60 uppercase">
            Overall confidence
          </span>
          <div className="font-mono text-[33px] leading-none font-bold tracking-[-0.03em]">
            {Math.round(confidence * 100)}
            <sup className="ml-px text-[15px] font-semibold text-white/75">%</sup>
          </div>
          <span
            className={cn(
              "mt-px flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 pl-1.75 text-[10.5px] font-semibold",
              pillClasses,
            )}
          >
            <span className={cn("size-1.5 rounded-full shadow-[0_0_0_3px_rgba(74,222,128,0.25)]", dotClasses)} />
            {copy.label}
          </span>
          <span className="mt-px font-mono text-[10.5px] text-white/72">
            {handleLineSubline(confidence, decision)}
          </span>
        </div>

        {/* RIGHT column */}
        <div className="flex min-w-0 flex-col justify-center gap-3">
          {/* Decision scale */}
          <div aria-label="Decision scale" className="relative">
            <div className="relative mt-7.5 flex h-1.75 rounded border border-white/15 bg-white/8">
              <span
                className="absolute -top-3.5 -translate-x-1/2 font-mono text-[9px] whitespace-nowrap text-white/60 after:absolute after:top-full after:left-1/2 after:mt-px after:h-1 after:w-px after:-translate-x-1/2 after:bg-white/30"
                style={{ left: `${ESCALATE_MAX * 100}%` }}
              >
                {ESCALATE_MAX.toFixed(2)}
              </span>
              <span
                className="absolute -top-3.5 -translate-x-1/2 font-mono text-[9px] whitespace-nowrap text-white/60 after:absolute after:top-full after:left-1/2 after:mt-px after:h-1 after:w-px after:-translate-x-1/2 after:bg-white/30"
                style={{ left: `${CLARIFY_MAX * 100}%` }}
              >
                {CLARIFY_MAX.toFixed(2)}
              </span>
              <div
                className="h-full rounded-l bg-destructive/40"
                style={{ width: `${ESCALATE_MAX * 100}%` }}
              />
              <div
                className="h-full bg-warning/40"
                style={{ width: `${(CLARIFY_MAX - ESCALATE_MAX) * 100}%` }}
              />
              <div
                className="h-full rounded-r bg-positive/35"
                style={{ width: `${(1 - CLARIFY_MAX) * 100}%` }}
              />
              <div
                className="absolute -top-1 z-3 flex -translate-x-1/2 flex-col items-center"
                style={{ left: `${confidence * 100}%` }}
              >
                <span className="relative bottom-0 mb-3 flex items-center gap-1 rounded-full bg-white px-1.75 py-0.5 font-mono text-[9.5px] font-bold whitespace-nowrap text-hero shadow-[0_2px_8px_rgba(0,0,0,0.28)] after:absolute after:top-full after:left-1/2 after:-translate-x-1/2 after:border-4 after:border-transparent after:border-t-white">
                  <MapPin className="size-2.25" />
                  {confidence.toFixed(2)}
                </span>
                <span className="h-[15px] w-[3px] rounded bg-white shadow-[0_0_0_2px_rgba(12,74,110,0.6),0_0_0_4px_rgba(255,255,255,0.18)]" />
              </div>
            </div>
            <div className="mt-1.75 flex justify-between font-mono text-[9px] text-white/62">
              <span>
                <span className="font-sans font-bold text-white/82">Escalate</span> 0–0.35
              </span>
              <span className="text-center">
                <span className="font-sans font-bold text-white/82">Clarify</span> 0.35–0.62
              </span>
              <span className="text-right">
                <span className="font-sans font-bold text-white/82">Handle</span> ≥ 0.62
              </span>
            </div>
          </div>

          {/* Stacked contribution bar */}
          <div aria-label="Confidence contribution breakdown" className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2.5">
              <div className="flex h-2.75 min-w-0 flex-1 overflow-hidden rounded border border-white/15 bg-white/8">
                <div
                  className="h-full bg-white/90"
                  style={{ width: `${clamp01(contribution.agreement) * 100}%` }}
                  title={`Label agreement +${contribution.agreement.toFixed(2)}`}
                />
                <div
                  className="h-full bg-[#BAE6FD]/70"
                  style={{ width: `${clamp01(contribution.score) * 100}%` }}
                  title={`Retrieval +${contribution.score.toFixed(2)}`}
                />
                {hasConsistency && (
                  <div
                    className="h-full bg-[#7DD3FC]/55"
                    style={{ width: `${clamp01(contribution.consistency) * 100}%` }}
                    title={`Model consistency +${contribution.consistency.toFixed(2)}`}
                  />
                )}
                <div
                  className="h-full border-l border-[#0C4A6E]/50 bg-[#F87171]/80"
                  style={{ width: `${clamp01(contribution.penalty) * 100}%` }}
                  title={`Missing-info −${contribution.penalty.toFixed(2)}`}
                />
              </div>
              <span className="shrink-0 font-mono text-xs font-bold">= {total.toFixed(2)}</span>
              <Collapsible open={open} onOpenChange={setOpen}>
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    aria-expanded={open}
                    className={cn(
                      // Fixed width + justify-between so the "Show"/"Hide" label swap never
                      // changes the button footprint and reflows the decision scale above.
                      "ml-1 flex w-[150px] shrink-0 items-center justify-between rounded-lg border border-white/24 bg-white/10 px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-white transition-colors hover:bg-white/18 hover:border-white/38 focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2",
                      open && "bg-white/16 border-white/32",
                    )}
                  >
                    {open ? "Hide breakdown" : "Show breakdown"}
                    <ChevronDown className={cn("size-3.5 transition-transform duration-200", open && "rotate-180")} />
                  </button>
                </CollapsibleTrigger>
              </Collapsible>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-white/80">
              <span className="inline-flex items-center gap-1.25">
                <span className="size-1.75 shrink-0 rounded-sm bg-white/90" />
                Label agreement <span className="font-mono font-semibold text-white">{contribution.agreement.toFixed(2)}</span>
              </span>
              <span className="inline-flex items-center gap-1.25">
                <span className="size-1.75 shrink-0 rounded-sm bg-[#BAE6FD]/70" />
                Retrieval <span className="font-mono font-semibold text-white">{contribution.score.toFixed(2)}</span>
              </span>
              {hasConsistency && (
                <span className="inline-flex items-center gap-1.25">
                  <span className="size-1.75 shrink-0 rounded-sm bg-[#7DD3FC]/55" />
                  Model consistency <span className="font-mono font-semibold text-white">{contribution.consistency.toFixed(2)}</span>
                </span>
              )}
              <span className="inline-flex items-center gap-1.25">
                <span className="size-1.75 shrink-0 rounded-sm bg-[#F87171]/80" />
                Missing info <span className="font-mono font-semibold text-white">−{contribution.penalty.toFixed(2)}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Full-width expanded breakdown */}
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleContent>
          <div className="mt-2.5 flex flex-col gap-2 border-t border-white/15 pt-2.5">
            <DetailRow label="Label agreement" value={contribution.agreement} raw={contribution.rawAgreement} sign="+" />
            <DetailRow label="Retrieval strength" value={contribution.score} raw={contribution.rawScore} sign="+" />
            {hasConsistency && (
              <DetailRow label="Model consistency" value={contribution.consistency} raw={contribution.rawConsistency} sign="+" />
            )}
            <DetailRow label="Missing-info penalty" value={contribution.penalty} raw={contribution.rawPenalty} sign="−" penalty />
            <div className="mt-1 flex items-center justify-between border-t border-dashed border-white/22 pt-2 text-[12.5px] font-bold">
              <span>Total confidence</span>
              <span className="font-mono text-sm">= {total.toFixed(2)}</span>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Slim action strip */}
      <div className="relative z-1 mt-2.75 flex items-center gap-2 rounded-md border border-white/15 bg-white/8 px-2.75 py-1.75 text-[12.5px] leading-snug text-white/92">
        <Lightbulb className="size-3.5 shrink-0 text-[#7DD3FC]" />
        <span>{renderLead(actionText)}</span>
      </div>
    </section>
  )
}

/** Bold the lead clause (before the em-dash) without using dangerouslySetInnerHTML —
 * `actionText` may embed backend-provided `clarification[0]` text. */
function renderLead(text: string): React.ReactNode {
  const idx = text.indexOf(" — ")
  if (idx === -1) return text
  return (
    <>
      <strong className="font-bold text-white">{text.slice(0, idx)}</strong>
      {text.slice(idx)}
    </>
  )
}

interface DetailRowProps {
  label: string
  value: number
  raw: number
  sign: "+" | "−"
  penalty?: boolean
}

function DetailRow({ label, value, raw, sign, penalty }: DetailRowProps) {
  return (
    <div className="grid grid-cols-[132px_1fr_48px] items-center gap-2.5">
      <span className="text-xs font-medium text-white/88">{label}</span>
      <div className="h-1.5 overflow-hidden rounded bg-white/10">
        <div
          className={cn("h-full rounded", penalty ? "bg-[#F87171]/85" : "bg-white/85")}
          style={{ width: `${clamp01(raw) * 100}%` }}
        />
      </div>
      <span className={cn("text-right font-mono text-xs font-bold", penalty && "text-[#FCA5A5]")}>
        {sign}
        {value.toFixed(2)}
      </span>
    </div>
  )
}
