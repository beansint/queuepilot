import { ClipboardCopy, ShieldAlert, UserPlus } from "lucide-react"
import { toast } from "sonner"
import type { AnalyzeResponse } from "@/lib/types"
import { CLARIFY_MAX, clamp01, formatPct, resolveMissingInfo, riskLabel } from "@/lib/derive"

interface EscalationPanelProps {
  response: AnalyzeResponse
  /** The original ticket text, so "Copy for handoff" can bundle it with the decision. */
  submittedText?: string
}

/**
 * Escalation panel — replaces the SuggestedReply card when the workflow routed a
 * ticket to a human (`resolveDecision(response) === "escalate"`). On the escalate
 * path the graph never runs `draft_reply`, so there is genuinely no reply to show
 * (a guardrail, not a bug). Rather than a hollow "no reply" reply card, this panel
 * explains *why* it escalated and offers the two actions that actually apply:
 * hand it to a teammate, or copy the ticket + decision for handoff elsewhere.
 *
 * Matches the console's light-card rhythm (the suggested-reply slot is a light
 * card) with a destructive accent so escalation reads at a glance — icon + text,
 * never colour alone.
 */
export function EscalationPanel({ response, submittedText }: EscalationPanelProps) {
  const confidence = clamp01(response.confidence)
  const slaRisk = response.sla_risk != null ? clamp01(response.sla_risk) : null
  const missing = resolveMissingInfo(response)
  const belowLine = Math.max(0, CLARIFY_MAX - confidence)

  async function handleCopy() {
    const lines = [
      "— QueuePilot escalation —",
      `Decision: Escalate to a human (confidence ${formatPct(confidence)}${
        slaRisk != null ? `, SLA risk ${slaRisk.toFixed(2)}` : ""
      })`,
      response.queue ? `Suggested queue: ${response.queue}` : null,
      response.priority ? `Priority: ${response.priority}` : null,
      missing.length ? `Missing before it can be handled: ${missing.join("; ")}` : null,
      submittedText ? `\nTicket:\n${submittedText}` : null,
    ].filter(Boolean)
    try {
      await navigator.clipboard.writeText(lines.join("\n"))
      toast.success("Copied ticket + decision for handoff")
    } catch {
      toast.error("Couldn't copy — copy the ticket text manually")
    }
  }

  return (
    <>
      <div className="mt-7 mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13.5px] font-bold tracking-[-0.005em]">
          <ShieldAlert className="size-[15px] text-destructive" />
          Escalation
        </h2>
        <span className="font-mono text-xs text-muted-foreground/80">Routed to a human — no auto-reply</span>
      </div>

      <section
        aria-label="Escalation"
        className="mb-2 overflow-hidden rounded-2xl border border-destructive/30 bg-card shadow-sm"
      >
        {/* Reason header — why the copilot held back. */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-destructive/[0.035] px-[22px] py-4">
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono text-[22px] font-bold tracking-[-0.01em] text-destructive tabular-nums">
              {formatPct(confidence)}
            </span>
            <span className="text-[12.5px] text-muted-foreground">
              confidence · {belowLine.toFixed(2)} below the handle line
            </span>
          </div>
          {slaRisk != null && (
            <span className="flex items-center gap-1.5 rounded-full bg-destructive/10 px-2.5 py-1 font-mono text-[11.5px] font-bold text-destructive">
              SLA risk {slaRisk.toFixed(2)}
              <span className="font-sans">· {riskLabel(slaRisk)}</span>
            </span>
          )}
        </div>

        <div className="px-[22px] py-5">
          <p className="text-[14.5px] leading-[1.6] tracking-[-0.006em] text-[#1E2534]">
            Confidence is too low to auto-handle safely, so QueuePilot didn't draft a reply — it routed
            this to a human instead of guessing.
          </p>

          {missing.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                Missing before it can be handled
              </div>
              <ul className="flex flex-col gap-1.5 border-l-2 border-destructive/40 py-0.5 pl-4">
                {missing.map((item, i) => (
                  <li key={i} className="text-[13.5px] leading-[1.6] tracking-[-0.006em] text-[#334155]">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-2.5 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => toast.success("Escalated — assigned to a teammate")}
              className="flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-primary-foreground transition-colors hover:bg-[#1E293B] hover:border-[#1E293B] focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              <UserPlus className="size-3.5" />
              Assign to teammate
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-white px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-foreground transition-colors hover:border-accent-foreground hover:text-accent-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              <ClipboardCopy className="size-3.5" />
              Copy for handoff
            </button>
          </div>
        </div>
      </section>
    </>
  )
}
