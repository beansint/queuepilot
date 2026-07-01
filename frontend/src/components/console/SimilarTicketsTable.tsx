import { GitCompareArrows } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { SimilarTicket } from "@/lib/types"
import { clamp01 } from "@/lib/derive"
import { cn } from "@/lib/utils"

interface SimilarTicketsTableProps {
  tickets: SimilarTicket[]
}

function priorityChipClass(priority: string | null): string {
  const p = priority?.toLowerCase()
  if (p === "high" || p === "urgent" || p === "critical") return "bg-destructive/10 text-destructive"
  if (p === "medium" || p === "med") return "bg-warning/15 text-warning"
  return "bg-secondary text-secondary-foreground"
}

export function SimilarTicketsTable({ tickets }: SimilarTicketsTableProps) {
  const maxScore = Math.max(0.001, ...tickets.map((t) => t.score))

  return (
    <>
      <div className="mt-7 mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13.5px] font-bold tracking-[-0.005em]">
          <GitCompareArrows className="size-[15px] text-accent-foreground" />
          Similar tickets
        </h2>
        <span className="font-mono text-xs text-muted-foreground/80">Ranked by retrieval score</span>
      </div>
      <section aria-label="Similar tickets evidence" className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        {tickets.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted-foreground">No similar tickets found.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-[#FBFCFD] hover:bg-[#FBFCFD]">
                <TableHead className="w-[110px] font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Score
                </TableHead>
                <TableHead className="font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Subject
                </TableHead>
                <TableHead className="w-[150px] font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Queue
                </TableHead>
                <TableHead className="w-[90px] font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Priority
                </TableHead>
                <TableHead className="w-[100px] font-mono text-[10.5px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
                  Type
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tickets.map((ticket, i) => (
                <TableRow key={i} className="hover:bg-[#FAFBFD]">
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <span className="w-[34px] shrink-0 font-mono text-sm font-bold text-accent-foreground">
                        {ticket.score.toFixed(2)}
                      </span>
                      <div className="h-1 w-14 shrink-0 overflow-hidden rounded-full bg-border">
                        <div
                          className="h-full rounded-full bg-accent-foreground"
                          style={{ width: `${(clamp01(ticket.score / maxScore)) * 100}%` }}
                        />
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="max-w-80 truncate font-semibold tracking-[-0.006em] text-foreground whitespace-normal">
                    {ticket.snippet}
                  </TableCell>
                  <TableCell className="text-sm">{ticket.queue ?? "—"}</TableCell>
                  <TableCell>
                    {ticket.priority ? (
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[11px] font-bold",
                          priorityChipClass(ticket.priority),
                        )}
                      >
                        {ticket.priority}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {ticket.type ? (
                      <span className="inline-block rounded-md bg-secondary px-2.25 py-0.75 text-[11px] font-semibold text-muted-foreground">
                        {ticket.type}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </>
  )
}
