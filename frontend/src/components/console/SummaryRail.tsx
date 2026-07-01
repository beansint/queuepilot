import { AlarmClock, AlertTriangle, Check, Gavel, Info, ListChecks, X } from "lucide-react"
import type { AnalyzeResponse } from "@/lib/types"
import { clamp01, decisionCopy, formatPct, resolveDecision, resolveMissingInfo, riskLabel } from "@/lib/derive"

interface SummaryRailProps {
  response: AnalyzeResponse
}

export function SummaryRail({ response }: SummaryRailProps) {
  const decision = resolveDecision(response)
  const copy = decisionCopy(decision)
  const slaRisk = clamp01(response.sla_risk ?? 0)
  const missing = resolveMissingInfo(response)

  const decisionIcon =
    decision === "handle" ? (
      <Check className="size-[19px] text-positive" />
    ) : decision === "clarify" ? (
      <AlertTriangle className="size-[19px] text-warning" />
    ) : (
      <X className="size-[19px] text-destructive" />
    )
  const decisionIconBg =
    decision === "handle" ? "bg-positive/10" : decision === "clarify" ? "bg-warning/15" : "bg-destructive/10"

  return (
    <aside
      aria-label="Summary"
      className="flex h-auto flex-col gap-4.5 border-t border-border px-5.5 py-5.5 md:hidden xl:sticky xl:top-0 xl:flex xl:h-screen xl:overflow-y-auto xl:border-t-0 xl:border-l"
    >
      <div className="font-mono text-[11px] font-bold tracking-[0.07em] text-muted-foreground/80 uppercase">
        Summary
      </div>

      <SummaryCard icon={<Gavel />} title="Decision">
        <div className="flex items-center gap-2.75">
          <div className={"flex size-9.5 shrink-0 items-center justify-center rounded-[10px] " + decisionIconBg}>
            {decisionIcon}
          </div>
          <div>
            <div className="text-[14.5px] font-bold tracking-[-0.01em]">
              {decision === "escalate" ? "Escalation" : decision === "clarify" ? "Clarification needed" : "No escalation"}
            </div>
            <div className="mt-0.25 text-xs text-muted-foreground">{copy.sub}</div>
          </div>
        </div>
      </SummaryCard>

      <SummaryCard icon={<AlarmClock />} title="SLA risk">
        {response.sla_risk != null ? (
          <>
            <div className="mb-1.5 flex items-baseline gap-2">
              <span className="font-mono text-[26px] font-bold text-destructive">{slaRisk.toFixed(2)}</span>
              <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-bold text-destructive">
                {riskLabel(slaRisk)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded border border-border bg-background">
              <div
                className="h-full rounded"
                style={{
                  width: `${slaRisk * 100}%`,
                  background: "linear-gradient(90deg,#F59E0B,#DC2626)",
                }}
              />
            </div>
            <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
              {slaRisk >= 0.66
                ? "High risk of breach — reply promptly to stay inside SLA."
                : slaRisk >= 0.33
                  ? "Moderate risk — keep an eye on response time."
                  : "Low risk of SLA breach."}
            </p>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">Not available</span>
        )}
      </SummaryCard>

      <SummaryCard icon={<ListChecks />} title="Missing info">
        {missing.length > 0 ? (
          <div className="flex flex-col gap-2.5">
            {missing.map((item, i) => (
              <div key={i} className="flex items-start gap-2.25 text-[12.5px] leading-relaxed text-[#334155]">
                <AlertTriangle className="mt-0.25 size-3.75 shrink-0 text-warning" />
                {item}
              </div>
            ))}
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">Nothing missing — ready to handle.</span>
        )}
      </SummaryCard>

      <SummaryCard icon={<Info />} title="At a glance">
        <MiniRow k="Category" v={response.category ?? "—"} />
        <MiniRow k="Queue" v={response.queue ?? "—"} />
        <MiniRow k="Priority" v={response.priority ?? "—"} />
        <MiniRow k="Confidence" v={formatPct(clamp01(response.confidence))} />
        <MiniRow k="Neighbors" v={String(response.similar_tickets.length)} />
      </SummaryCard>
    </aside>
  )
}

function SummaryCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 px-[17px] shadow-sm">
      <div className="mb-2.5 flex items-center gap-1.75 font-mono text-[11.5px] font-bold tracking-[0.04em] text-muted-foreground uppercase">
        <span className="[&_svg]:size-3.5">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  )
}

function MiniRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-1.75 text-[12.5px] last:border-b-0">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono font-semibold text-foreground">{v}</span>
    </div>
  )
}
