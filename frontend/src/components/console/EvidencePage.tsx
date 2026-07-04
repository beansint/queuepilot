import { ArrowLeft, GitCompareArrows } from "lucide-react"
import type { AnalyzeResponse } from "@/lib/types"
import { clamp01 } from "@/lib/derive"
import { cn } from "@/lib/utils"

interface EvidencePageProps {
  response: AnalyzeResponse
  /** The analyzed ticket text, shown for context at the top of the page. */
  submittedText?: string
  /** Return to the console (analysis) view. */
  onBack: () => void
}

function priorityChipClass(priority: string | null): string {
  const p = priority?.toLowerCase()
  if (p === "high" || p === "urgent" || p === "critical") return "bg-destructive/10 text-destructive"
  if (p === "medium" || p === "med") return "bg-warning/15 text-warning"
  return "bg-secondary text-secondary-foreground"
}

/**
 * Full-page evidence view (route `#/evidence`): every retrieved neighbour that
 * grounded the analysis, ranked by retrieval score, with the **full** snippet
 * (the inline console table truncates). Modelled on ranked-evidence detail views
 * (e.g. Elicit) — score bar + tabular figure + metadata per row.
 *
 * Only reachable once an analysis exists; App redirects to the console otherwise.
 */
export function EvidencePage({ response, submittedText, onBack }: EvidencePageProps) {
  const tickets = response.similar_tickets
  const maxScore = Math.max(0.001, ...tickets.map((t) => t.score))

  return (
    <main className="w-full max-w-full min-w-0 px-4 pt-5.5 pb-15 sm:px-8 md:max-w-[920px]">
      <button
        type="button"
        onClick={onBack}
        className="mb-5 flex items-center gap-1.5 rounded text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
      >
        <ArrowLeft className="size-3.5" />
        Back to analysis
      </button>

      <div className="mb-6.5 flex items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[19px] font-bold tracking-[-0.02em]">
            <GitCompareArrows className="size-[18px] text-accent-foreground" />
            Evidence
          </div>
          <div className="mt-0.5 text-[13px] text-muted-foreground">
            {tickets.length} similar {tickets.length === 1 ? "ticket" : "tickets"} · ranked by retrieval score
          </div>
        </div>
      </div>

      {submittedText && (
        <section
          aria-label="Analyzed ticket"
          className="mb-6 rounded-2xl border border-border bg-card p-5 px-[22px] shadow-sm"
        >
          <div className="mb-2 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
            Analyzed ticket
          </div>
          <p className="text-[14px] leading-[1.65] tracking-[-0.006em] text-[#334155]">{submittedText}</p>
        </section>
      )}

      {tickets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card/50 p-10 text-center text-sm text-muted-foreground">
          No similar tickets were retrieved for this analysis.
        </div>
      ) : (
        <ol className="flex flex-col gap-3">
          {tickets.map((ticket, i) => (
            <li
              key={i}
              className="rounded-2xl border border-border bg-card p-5 px-[22px] shadow-sm transition-colors hover:border-accent-foreground/40"
            >
              <div className="mb-3 flex items-center gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary font-mono text-[11px] font-bold text-muted-foreground">
                  {i + 1}
                </span>
                <span className="w-[38px] shrink-0 font-mono text-sm font-bold text-accent-foreground tabular-nums">
                  {ticket.score.toFixed(2)}
                </span>
                <div className="h-1.5 w-full max-w-[220px] overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full rounded-full bg-accent-foreground"
                    style={{ width: `${clamp01(ticket.score / maxScore) * 100}%` }}
                  />
                </div>
              </div>

              <p className="text-[14px] leading-[1.65] tracking-[-0.006em] text-foreground">{ticket.snippet}</p>

              <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-border pt-3">
                <span className="font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/70 uppercase">
                  {ticket.queue ?? "—"}
                </span>
                {ticket.priority && (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[11px] font-bold",
                      priorityChipClass(ticket.priority),
                    )}
                  >
                    {ticket.priority}
                  </span>
                )}
                {ticket.type && (
                  <span className="inline-block rounded-md bg-secondary px-2.25 py-0.75 text-[11px] font-semibold text-muted-foreground">
                    {ticket.type}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </main>
  )
}
