import { ArrowUpRight, FolderGit2, Hash, Timer } from "lucide-react"
import type { TraceSummary } from "@/lib/types"

interface TraceStripProps {
  trace: TraceSummary | null
}

export function TraceStrip({ trace }: TraceStripProps) {
  const enabled = trace?.enabled ?? false

  return (
    <div className="mt-5">
      <div className="flex w-full flex-wrap items-center gap-5 rounded-xl border border-border bg-card px-4.5 py-3 shadow-sm">
        <div className="flex items-center gap-1.5 text-[12.5px] font-bold text-muted-foreground">
          <span
            className={
              "size-1.5 rounded-full " +
              (enabled ? "bg-positive shadow-[0_0_0_3px_var(--positive)]/20" : "bg-muted-foreground/40")
            }
          />
          <span className={enabled ? "text-positive" : "text-muted-foreground"}>
            {enabled ? "Traced" : "Tracing off"}
          </span>
        </div>
        {enabled && (
          <>
            <div className="flex items-center gap-1.75 text-[12.5px] text-muted-foreground">
              <Hash className="size-3.5" />
              run_id <span className="font-mono font-semibold text-foreground">{trace?.run_id ?? "—"}</span>
            </div>
            <div className="flex items-center gap-1.75 text-[12.5px] text-muted-foreground">
              <Timer className="size-3.5" />
              latency{" "}
              <span className="font-mono font-semibold text-foreground">
                {trace?.latency_ms != null ? `${Math.round(trace.latency_ms).toLocaleString()} ms` : "—"}
              </span>
            </div>
            <div className="flex items-center gap-1.75 text-[12.5px] text-muted-foreground">
              <FolderGit2 className="size-3.5" />
              project <span className="font-mono font-semibold text-foreground">{trace?.project ?? "—"}</span>
            </div>
          </>
        )}
        <div className="flex-1" />
        {enabled && trace?.url && (
          <a
            href={trace.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-1.25 text-[12.5px] font-bold text-accent-foreground transition-all hover:gap-2"
          >
            View in LangSmith
            <ArrowUpRight className="size-3.25" />
          </a>
        )}
      </div>
    </div>
  )
}
