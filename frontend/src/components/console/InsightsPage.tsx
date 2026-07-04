import { useEffect, useMemo, useState } from "react"
import { AlertCircle, ArrowLeft, BarChart3, Gauge, ListChecks, Percent, Target } from "lucide-react"
import type { SnapshotCard, SnapshotSummary } from "@/lib/types"
import { AuthRequiredError, getEvalSnapshot, getEvalSnapshots } from "@/lib/api"
import { cn } from "@/lib/utils"

interface InsightsPageProps {
  /** Return to the console (analysis) view. */
  onBack: () => void
  /** Same auth-expiry handling as the rest of the console (401 -> re-gate to login). */
  onAuthExpired: () => void
}

type LoadState = "loading" | "empty" | "error" | "ready"

/** Percent-metric rows shown as the headline metric grid — label + the SnapshotMetrics key
 * it reads. Mirrors app/eval_api.py::SnapshotMetrics / eval/card.py's _PERCENT_METRICS. */
const HEADLINE_METRICS: { key: "queue_match" | "priority_match" | "type_match" | "label_recall_at_k" | "reply_quality"; label: string; icon: React.ReactNode }[] = [
  { key: "queue_match", label: "Queue exact-match", icon: <Target /> },
  { key: "priority_match", label: "Priority exact-match", icon: <Target /> },
  { key: "type_match", label: "Type exact-match", icon: <Target /> },
  { key: "label_recall_at_k", label: "Label recall@k", icon: <ListChecks /> },
  { key: "reply_quality", label: "Judge mean (reply quality)", icon: <Gauge /> },
]

function formatPctOrNa(value: number | null): string {
  if (value == null) return "n/a"
  return `${(value * 100).toFixed(1)}%`
}

/** Same three-zone color scale as ConfidenceHero's decision pill (destructive / warning /
 * positive), applied to a plain [0,1] score rather than the confidence-specific bands. */
function scoreColorClass(value: number | null): string {
  if (value == null) return "text-muted-foreground"
  if (value >= 0.66) return "text-positive"
  if (value >= 0.33) return "text-warning"
  return "text-destructive"
}

export function InsightsPage({ onBack, onAuthExpired }: InsightsPageProps) {
  const [state, setState] = useState<LoadState>("loading")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [summaries, setSummaries] = useState<SnapshotSummary[]>([])
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [card, setCard] = useState<SnapshotCard | null>(null)
  const [cardError, setCardError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setState("loading")
      setErrorMessage(null)
      try {
        const { snapshots } = await getEvalSnapshots()
        if (cancelled) return
        if (snapshots.length === 0) {
          setState("empty")
          return
        }
        setSummaries(snapshots)
        setSelectedName(snapshots[0].name)
        setState("ready")
      } catch (err) {
        if (cancelled) return
        if (err instanceof AuthRequiredError) {
          onAuthExpired()
          return
        }
        setErrorMessage(err instanceof Error ? err.message : "Couldn't load eval snapshots.")
        setState("error")
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [onAuthExpired])

  useEffect(() => {
    if (!selectedName) return
    let cancelled = false
    async function loadCard(name: string) {
      setCard(null)
      setCardError(null)
      try {
        const result = await getEvalSnapshot(name)
        if (cancelled) return
        setCard(result)
      } catch (err) {
        if (cancelled) return
        if (err instanceof AuthRequiredError) {
          onAuthExpired()
          return
        }
        setCardError(err instanceof Error ? err.message : "Couldn't load this snapshot.")
      }
    }
    void loadCard(selectedName)
    return () => {
      cancelled = true
    }
  }, [selectedName, onAuthExpired])

  const metrics = card?.metrics ?? null
  const configEntries = useMemo(
    () => Object.entries(metrics?.config ?? {}).map(([k, v]) => `${k}=${String(v)}`),
    [metrics],
  )

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
            <BarChart3 className="size-[18px] text-accent-foreground" />
            Insights
          </div>
          <div className="mt-0.5 text-[13px] text-muted-foreground">
            Eval snapshot metrics — grounded in committed offline/online eval runs, not live traffic.
          </div>
        </div>
      </div>

      {state === "loading" && (
        <div
          aria-busy="true"
          className="flex flex-col gap-3 rounded-2xl border border-dashed border-border bg-card/50 px-6 py-16 text-center"
        >
          <p className="text-sm font-medium text-muted-foreground">Loading eval snapshots…</p>
        </div>
      )}

      {state === "empty" && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-card/50 px-6 py-16 text-center">
          <div className="flex size-11 items-center justify-center rounded-full bg-accent">
            <BarChart3 className="size-5 text-accent-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground">No eval snapshots yet</p>
          <p className="max-w-sm text-[13px] text-muted-foreground">
            Run an offline or online eval (see <code>eval/run_experiment.py</code>) to generate a snapshot card
            under <code>eval/snapshots/</code>.
          </p>
        </div>
      )}

      {state === "error" && (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-5 py-4.5">
          <div className="flex items-center gap-2 text-sm font-semibold text-destructive">
            <AlertCircle className="size-4" />
            Couldn't load eval snapshots
          </div>
          <p className="text-[13px] text-muted-foreground">{errorMessage}</p>
        </div>
      )}

      {state === "ready" && (
        <>
          {summaries.length > 1 && (
            <div className="mb-5 flex flex-wrap items-center gap-2">
              {summaries.map((s) => (
                <button
                  key={s.name}
                  type="button"
                  onClick={() => setSelectedName(s.name)}
                  aria-pressed={selectedName === s.name}
                  className={cn(
                    "rounded-full border px-3 py-1.5 font-mono text-[12px] font-semibold transition-colors",
                    selectedName === s.name
                      ? "border-accent-foreground/50 bg-accent text-accent-foreground"
                      : "border-border bg-card text-muted-foreground hover:border-accent-foreground/30 hover:text-foreground",
                  )}
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}

          {cardError && (
            <div className="mb-5 flex flex-col items-start gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 px-5 py-4.5">
              <div className="flex items-center gap-2 text-sm font-semibold text-destructive">
                <AlertCircle className="size-4" />
                Couldn't load this snapshot
              </div>
              <p className="text-[13px] text-muted-foreground">{cardError}</p>
            </div>
          )}

          {!cardError && !metrics && (
            <div aria-busy="true" className="mb-5 rounded-2xl border border-dashed border-border bg-card/50 px-6 py-10 text-center text-sm text-muted-foreground">
              Loading snapshot…
            </div>
          )}

          {metrics && (
            <>
              <section
                aria-label="Snapshot summary"
                className="mb-6 rounded-2xl border border-border bg-card p-5 px-[22px] shadow-sm"
              >
                <div className="mb-2 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Run config
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[#334155]">
                  <span>
                    <span className="font-semibold text-foreground">N</span> = {metrics.n ?? "n/a"}
                  </span>
                  {configEntries.length > 0 && (
                    <span className="font-mono text-[12px] text-muted-foreground">{configEntries.join(", ")}</span>
                  )}
                </div>
                {metrics.skipped_evaluators.length > 0 && (
                  <p className="mt-2 text-[12px] text-muted-foreground">
                    Skipped evaluators (not run for this snapshot): {metrics.skipped_evaluators.join(", ")}
                  </p>
                )}
              </section>

              <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {HEADLINE_METRICS.map((m) => {
                  const value = metrics[m.key]
                  return (
                    <div key={m.key} className="rounded-xl border border-border bg-card p-4 px-[17px] shadow-sm">
                      <div className="mb-2 flex items-center gap-1.75 font-mono text-[10.5px] font-bold tracking-[0.04em] text-muted-foreground uppercase">
                        <span className="[&_svg]:size-3.5">{m.icon}</span>
                        {m.label}
                      </div>
                      <div className={cn("font-mono text-[22px] font-bold tabular-nums", scoreColorClass(value))}>
                        {formatPctOrNa(value)}
                      </div>
                    </div>
                  )
                })}

                <div className="rounded-xl border border-border bg-card p-4 px-[17px] shadow-sm">
                  <div className="mb-2 flex items-center gap-1.75 font-mono text-[10.5px] font-bold tracking-[0.04em] text-muted-foreground uppercase">
                    <span className="[&_svg]:size-3.5">
                      <Percent />
                    </span>
                    Expected Calibration Error
                  </div>
                  <div className="font-mono text-[22px] font-bold tabular-nums text-foreground">
                    {metrics.ece != null ? metrics.ece.toFixed(4) : "n/a"}
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">Lower is better — 0 is perfectly calibrated.</p>
                </div>
              </div>

              <section aria-label="Reliability table" className="rounded-2xl border border-border bg-card p-5 px-[22px] shadow-sm">
                <div className="mb-3 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Reliability table
                </div>
                {metrics.reliability.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No reliability buckets in this snapshot.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[420px] text-left text-[13px]">
                      <thead>
                        <tr className="border-b border-border text-[11px] font-bold tracking-[0.04em] text-muted-foreground uppercase">
                          <th className="py-2 pr-3 font-mono">Bucket</th>
                          <th className="py-2 pr-3 font-mono">N</th>
                          <th className="py-2 pr-3 font-mono">Claimed</th>
                          <th className="py-2 pr-3 font-mono">Accuracy</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.reliability.map((row, i) => {
                          const gap =
                            row.claimed != null && row.accuracy != null
                              ? Math.abs(row.claimed - row.accuracy)
                              : null
                          return (
                            <tr key={i} className="border-b border-border last:border-b-0">
                              <td className="py-2 pr-3 font-mono tabular-nums text-foreground">
                                [{row.lo.toFixed(2)}, {row.hi.toFixed(2)})
                              </td>
                              <td className="py-2 pr-3 font-mono tabular-nums text-muted-foreground">{row.n}</td>
                              <td className="py-2 pr-3 font-mono tabular-nums text-muted-foreground">
                                {formatPctOrNa(row.claimed)}
                              </td>
                              <td
                                className={cn(
                                  "py-2 pr-3 font-mono font-semibold tabular-nums",
                                  gap != null && gap > 0.2 ? "text-destructive" : "text-foreground",
                                )}
                              >
                                {formatPctOrNa(row.accuracy)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}
        </>
      )}
    </main>
  )
}
