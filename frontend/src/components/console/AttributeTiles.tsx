import { Flag, HeartPulse, Route, Tag } from "lucide-react"
import type { AnalyzeResponse } from "@/lib/types"
import { clamp01, sentimentLabel } from "@/lib/derive"
import { cn } from "@/lib/utils"

interface AttributeTilesProps {
  response: AnalyzeResponse
}

function priorityChipClass(priority: string | null): string {
  const p = priority?.toLowerCase()
  if (p === "high" || p === "urgent" || p === "critical") return "bg-destructive/10 text-destructive"
  if (p === "medium" || p === "med") return "bg-warning/15 text-warning"
  return "bg-secondary text-secondary-foreground"
}

function Chip({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-mono text-[11px] font-bold",
        className,
      )}
    >
      {children}
    </span>
  )
}

function Tile({
  icon,
  label,
  sub,
  children,
  className,
}: {
  icon: React.ReactNode
  label: string
  sub: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-3.5 px-[15px] shadow-sm transition-all hover:-translate-y-px hover:shadow-md",
        className,
      )}
    >
      <div className="mb-2 flex items-center gap-1.5 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
        <span className="[&_svg]:size-3">{icon}</span>
        {label}
      </div>
      <div className="flex items-center gap-2 text-base font-bold tracking-[-0.01em]">{children}</div>
      <div className="mt-1 font-mono text-[11.5px] text-muted-foreground">{sub}</div>
    </div>
  )
}

export function AttributeTiles({ response }: AttributeTilesProps) {
  const frustration = clamp01(response.sentiment?.frustration ?? 0)
  const negativity = clamp01(response.sentiment?.negativity ?? 0)

  return (
    <section aria-label="Ticket attributes" className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Tile icon={<Tag />} label="Classification" sub="Type">
        {response.category ? (
          <Chip className="bg-secondary text-secondary-foreground">{response.category}</Chip>
        ) : (
          <span className="text-sm text-muted-foreground">Unclassified</span>
        )}
      </Tile>
      <Tile icon={<Route />} label="Routing" sub="Queue">
        {response.queue ? (
          <Chip className="bg-accent text-accent-foreground">{response.queue}</Chip>
        ) : (
          <span className="text-sm text-muted-foreground">Unrouted</span>
        )}
      </Tile>
      <Tile icon={<Flag />} label="Priority" sub="SLA tier">
        {response.priority ? (
          <Chip className={priorityChipClass(response.priority)}>{response.priority}</Chip>
        ) : (
          <span className="text-sm text-muted-foreground">Unset</span>
        )}
      </Tile>

      <div className="rounded-xl border border-border bg-card p-3.5 px-[15px] shadow-sm sm:col-span-3">
        <div className="mb-2 flex items-center gap-1.5 font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
          <HeartPulse className="size-3" />
          Sentiment
        </div>
        {response.sentiment ? (
          <div className="flex flex-col gap-2.75">
            <SentimentRow label="Frustration" value={frustration} color="var(--destructive)" />
            <SentimentRow label="Negativity" value={negativity} color="var(--warning)" />
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">Not available</span>
        )}
      </div>
    </section>
  )
}

function SentimentRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex justify-between text-xs font-semibold">
        <span>{label}</span>
        <span className="font-mono font-semibold text-muted-foreground">
          {value.toFixed(2)} · {sentimentLabel(value)}
        </span>
      </div>
      <div className="mt-1 h-1.25 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full"
          style={{ width: `${value * 100}%`, background: color }}
        />
      </div>
    </div>
  )
}
