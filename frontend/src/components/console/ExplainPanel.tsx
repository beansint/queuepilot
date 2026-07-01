import { forwardRef } from "react"
import { BrainCircuit, ChevronDown } from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { AnalyzeResponse } from "@/lib/types"
import { clamp01, confidenceContribution, slaContribution } from "@/lib/derive"
import { cn } from "@/lib/utils"

interface ExplainPanelProps {
  response: AnalyzeResponse
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const ExplainPanel = forwardRef<HTMLButtonElement, ExplainPanelProps>(function ExplainPanel(
  { response, open, onOpenChange },
  ref,
) {
  const debug = response.debug
  if (!debug) return null

  const confidence = confidenceContribution(debug.confidence_breakdown)
  const sla = slaContribution(debug.sla_breakdown)
  const hasConsistency = confidence.consistency > 0.001

  return (
    <Collapsible
      open={open}
      onOpenChange={onOpenChange}
      className="mt-5 overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
    >
      <CollapsibleTrigger asChild>
        <button
          ref={ref}
          type="button"
          aria-expanded={open}
          className="flex w-full items-center justify-between px-5 py-4 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        >
          <div className="flex items-center gap-2.25">
            <BrainCircuit className="size-[17px] text-accent-foreground" />
            <div>
              <div className="text-sm font-bold tracking-[-0.01em]">
                Explain this analysis{" "}
                <span className="ml-2.5 rounded-md border border-border bg-background px-1.75 py-0.5 font-mono text-[10.5px] text-muted-foreground">
                  E
                </span>
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                Node trace, confidence and SLA breakdowns
              </div>
            </div>
          </div>
          <ChevronDown className={cn("size-[18px] shrink-0 text-muted-foreground transition-transform duration-250", open && "rotate-180")} />
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="border-t border-border px-5 pt-1 pb-6">
          <SubHeading>Node trace</SubHeading>
          <div className="flex flex-col">
            {debug.nodes.map((node, i) => (
              <div key={node.name} className="flex gap-3.5 pb-4.5 last:pb-0">
                <div className="flex flex-shrink-0 flex-col items-center">
                  <div className="mt-1.25 size-2.25 shrink-0 rounded-full bg-accent-foreground shadow-[0_0_0_3px_var(--accent)]" />
                  {i < debug.nodes.length - 1 && <div className="mt-1 w-[1.5px] flex-1 bg-border" />}
                </div>
                <div className="pb-0.5">
                  <div className="mb-0.75 font-mono text-[12.5px] font-bold text-accent-foreground">
                    {node.name}
                  </div>
                  <div className="text-[13px] leading-normal text-[#334155]">{node.rationale}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-7 md:grid-cols-2">
            <div>
              <SubHeading>Confidence breakdown</SubHeading>
              <div className="flex flex-col gap-2.5">
                <BreakdownRow label="Label agreement" raw={confidence.rawAgreement} value={confidence.agreement} sign="+" />
                <BreakdownRow label="Retrieval strength" raw={confidence.rawScore} value={confidence.score} sign="+" />
                {hasConsistency && (
                  <BreakdownRow
                    label="LLM/majority consistency"
                    raw={confidence.rawConsistency}
                    value={confidence.consistency}
                    sign="+"
                  />
                )}
                <BreakdownRow label="Missing-info penalty" raw={confidence.rawPenalty} value={confidence.penalty} sign="−" tone="negative" />
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-dashed border-[#CBD5E1] pt-3 text-[13.5px] font-bold">
                <span>Total confidence</span>
                <span className="font-mono text-base text-accent-foreground">
                  = {(debug.confidence_breakdown.final || response.confidence).toFixed(2)}
                </span>
              </div>
            </div>

            <div>
              <SubHeading>SLA breakdown</SubHeading>
              <div className="flex flex-col gap-2.5">
                <BreakdownRow
                  label={`Priority (${debug.sla_breakdown.priority ?? "—"})`}
                  raw={sla.rawPriority}
                  value={sla.priority}
                  sign="+"
                  tone="amber"
                />
                <BreakdownRow label="Frustration" raw={sla.rawFrustration} value={sla.frustration} sign="+" tone="amber" />
                <BreakdownRow label="Missing info" raw={sla.rawMissing} value={sla.missing} sign="+" tone="amber" />
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-dashed border-[#CBD5E1] pt-3 text-[13.5px] font-bold">
                <span>Total SLA risk</span>
                <span className="font-mono text-base text-destructive">
                  = {(debug.sla_breakdown.final ?? response.sla_risk ?? 0).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
})

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-5 mb-3 font-mono text-[11px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase first:mt-0.5">
      {children}
    </div>
  )
}

function BreakdownRow({
  label,
  raw,
  value,
  sign,
  tone = "positive",
}: {
  label: string
  raw: number
  value: number
  sign: "+" | "−"
  tone?: "positive" | "negative" | "amber"
}) {
  const fillClass =
    tone === "negative" ? "bg-destructive" : tone === "amber" ? "bg-warning" : "bg-positive"
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 sm:grid-cols-[168px_1fr_64px]">
      <div className="text-[13px] font-medium">{label}</div>
      <div className="col-span-2 h-2 overflow-hidden rounded border border-border bg-background sm:col-span-1">
        <div className={cn("h-full rounded", fillClass)} style={{ width: `${clamp01(raw) * 100}%` }} />
      </div>
      <div className="text-right font-mono text-[12.5px] font-bold">
        {sign}
        {value.toFixed(2)}
      </div>
    </div>
  )
}
