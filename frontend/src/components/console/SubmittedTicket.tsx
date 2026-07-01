import { FileText } from "lucide-react"

interface SubmittedTicketProps {
  text: string
  id: string
  timestamp: string
}

export function SubmittedTicket({ text, id, timestamp }: SubmittedTicketProps) {
  return (
    <section aria-label="Submitted ticket" className="mb-5 rounded-2xl border border-border bg-card p-[18px_20px] shadow-sm">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase">
          <FileText className="size-3.5" />
          Submitted ticket
        </div>
        <div className="font-mono text-[11.5px] text-muted-foreground/80">
          #{id} · {timestamp}
        </div>
      </div>
      <p className="text-[15px] leading-relaxed tracking-[-0.006em] text-[#1E2534]">"{text}"</p>
    </section>
  )
}
